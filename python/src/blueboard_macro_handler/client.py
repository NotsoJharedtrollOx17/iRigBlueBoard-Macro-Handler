from __future__ import annotations

import asyncio
import logging
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .ble_midi import BleMidiDecoder
from .models import ConnectionState, MidiEvent, RunMetrics
from .state import saveLastAddress

serviceUuid = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
midiCharacteristicUuid = "7772e5db-3868-4112-a1a9-f2669d106bf3"
blueBoardMidiValueHandle = "0x0022"
blueBoardMidiCccHandle = "0x0023"
logger = logging.getLogger("blueboard.client")
gatttoolNotificationPattern = re.compile(
    rf"(?:Notification|Indication) handle = {blueBoardMidiValueHandle} value:\s*(?P<value>(?:[0-9a-fA-F]{{2}}\s*)+)$",
    re.IGNORECASE,
)


class BluezMidiServiceOmitted(RuntimeError):
    def __init__(self, address: str) -> None:
        super().__init__("BlueZ omitted the advertised BLE-MIDI service")
        self.address = address


def parseGatttoolNotification(line: str) -> bytes | None:
    match = gatttoolNotificationPattern.search(line.strip())
    if match is None:
        return None
    try:
        return bytes.fromhex(match.group("value"))
    except ValueError:
        return None


@dataclass(frozen=True)
class DiscoveredDevice:
    name: str | None
    address: str
    rssi: int | None
    device: object


async def discoverBlueBoards(nameSubstring: str, timeout: float) -> list[DiscoveredDevice]:
    try:
        from bleak import BleakScanner
    except ImportError as error:
        raise RuntimeError("Bleak is not installed; install blueboard-macro-handler") from error
    found: dict[str, DiscoveredDevice] = {}
    def detected(device, advertisementData) -> None:
        name = advertisementData.local_name or device.name
        services = {value.lower() for value in advertisementData.service_uuids}
        if (name and nameSubstring.casefold() in name.casefold()) or serviceUuid in services:
            found[device.address] = DiscoveredDevice(name, device.address, advertisementData.rssi, device)
    async with BleakScanner(detection_callback=detected):
        await asyncio.sleep(timeout)
    return sorted(found.values(), key=lambda item: item.name or "")


class BlueBoardClient:
    def __init__(self, eventHandler: Callable[[MidiEvent], None], disconnectHandler: Callable[[], None], *, nameSubstring: str, address: str | None, pair: bool, scanTimeout: float, metrics: RunMetrics | None = None, statePath: Path | None = None) -> None:
        self.eventHandler, self.disconnectHandler = eventHandler, disconnectHandler
        self.nameSubstring, self.address, self.pair, self.scanTimeout = nameSubstring, address, pair, scanTimeout
        self.metrics, self.statePath = metrics or RunMetrics(), statePath
        self.decoder, self.writeLock = BleMidiDecoder(), asyncio.Lock()
        self.currentClient = None

    def transition(self, state: ConnectionState, **fields) -> None:
        details = " ".join(f"{key}={value}" for key, value in fields.items())
        logger.info("state=%s%s", state.value, f" {details}" if details else "")

    async def findDevice(self):
        devices = await discoverBlueBoards(self.nameSubstring, self.scanTimeout)
        if self.address:
            matched = [item for item in devices if item.address.casefold() == self.address.casefold()]
            if matched:
                devices = matched
            else:
                logger.warning("saved address=%s was not found; falling back to name/service match", self.address)
        if not devices:
            raise RuntimeError("BlueBoard not found; hold C while powering it on")
        selected = devices[0]
        logger.info("discovered name=%s address=%s RSSI=%s", selected.name, selected.address, selected.rssi)
        return selected.device

    async def writePacket(self, packet: bytes, response: bool = False) -> None:
        if self.currentClient is None or not self.currentClient.is_connected:
            raise RuntimeError("BlueBoard is not connected")
        async with self.writeLock:
            await self.currentClient.write_gatt_char(midiCharacteristicUuid, packet, response=response)

    def handlePacket(self, packet: bytes) -> None:
        self.metrics.packets += 1
        logger.debug("packet=%s", packet.hex(" "))
        for event in self.decoder.decode(packet):
            try: self.eventHandler(event)
            except Exception: logger.exception("event handler failed; continuing")

    async def runBluezGatttoolFallback(self, address: str, stopEvent: asyncio.Event) -> None:
        gatttool = shutil.which("gatttool")
        if gatttool is None:
            raise RuntimeError("BlueZ omitted the BLE-MIDI service and gatttool is unavailable; install the full bluez package")
        command = [gatttool, "-b", address, "--char-write-req", f"--handle={blueBoardMidiCccHandle}", "--value=0100", "--listen"]
        stdbuf = shutil.which("stdbuf")
        if stdbuf is not None:
            command = [stdbuf, "-oL", "-eL", *command]
        logger.warning("BlueZ D-Bus omitted the advertised BLE-MIDI service; using the BlueZ gatttool compatibility path")
        self.transition(ConnectionState.subscribing, backend="bluez-gatttool", characteristic=blueBoardMidiValueHandle)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if process.stdout is None:
            raise RuntimeError("could not capture gatttool output")
        stopTask = asyncio.create_task(stopEvent.wait())
        subscribed = False
        try:
            while True:
                lineTask = asyncio.create_task(process.stdout.readline())
                done, _pending = await asyncio.wait((lineTask, stopTask), return_when=asyncio.FIRST_COMPLETED)
                if stopTask in done:
                    lineTask.cancel()
                    await asyncio.gather(lineTask, return_exceptions=True)
                    return
                line = lineTask.result()
                if not line:
                    returnCode = await process.wait()
                    raise RuntimeError(f"gatttool compatibility connection ended with status {returnCode}")
                message = line.decode(errors="replace").strip()
                logger.debug("gatttool=%s", message)
                if not subscribed and "Characteristic value was written successfully" in message:
                    subscribed = True
                    self.metrics.beginConnection()
                    self.transition(ConnectionState.connected, address=address, backend="bluez-gatttool")
                    if self.statePath:
                        try: saveLastAddress(self.statePath, address)
                        except OSError as error: logger.warning("could not save device state: %s", error)
                    continue
                packet = parseGatttoolNotification(message)
                if packet is not None:
                    self.handlePacket(packet)
        finally:
            stopTask.cancel()
            await asyncio.gather(stopTask, return_exceptions=True)
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

    async def run(self, stopEvent: asyncio.Event | None = None) -> None:
        from bleak import BleakClient
        stopEvent = stopEvent or asyncio.Event()
        retryDelay, retryCount = 1.0, 0
        while not stopEvent.is_set():
            disconnected, eventQueue = asyncio.Event(), asyncio.Queue(maxsize=1024)
            worker = None
            try:
                self.transition(ConnectionState.scanning, retry=retryCount)
                device = await self.findDevice()
                self.transition(ConnectionState.connecting, pair=self.pair)
                def onDisconnected(_client, event=disconnected) -> None: event.set()
                async with BleakClient(device, disconnected_callback=onDisconnected, services=[serviceUuid], pair=self.pair, timeout=45.0 if self.pair else 30.0) as client:
                    self.currentClient = client
                    self.transition(ConnectionState.discovering)
                    if client.services.get_service(serviceUuid) is None:
                        if sys.platform.startswith("linux"):
                            raise BluezMidiServiceOmitted(device.address)
                        raise RuntimeError("BLE-MIDI service was not discovered")
                    self.transition(ConnectionState.subscribing, characteristic=midiCharacteristicUuid)
                    def onNotification(_characteristic, data: bytearray, queue=eventQueue) -> None:
                        try: queue.put_nowait(bytes(data))
                        except asyncio.QueueFull: logger.error("notification queue full; packet dropped")
                    async def consumeNotifications(queue=eventQueue) -> None:
                        while True:
                            packet = await queue.get()
                            self.handlePacket(packet)
                    worker = asyncio.create_task(consumeNotifications(), name="blueboard-notifications")
                    await client.start_notify(midiCharacteristicUuid, onNotification)
                    self.transition(ConnectionState.connected, address=device.address)
                    self.metrics.beginConnection()
                    if self.statePath:
                        try: saveLastAddress(self.statePath, device.address)
                        except OSError as error: logger.warning("could not save device state: %s", error)
                    retryDelay, retryCount = 1.0, 0
                    stopTask, disconnectTask = asyncio.create_task(stopEvent.wait()), asyncio.create_task(disconnected.wait())
                    _done, pending = await asyncio.wait((stopTask, disconnectTask), return_when=asyncio.FIRST_COMPLETED)
                    for task in pending: task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    if client.is_connected:
                        await client.stop_notify(midiCharacteristicUuid)
            except asyncio.CancelledError:
                raise
            except BluezMidiServiceOmitted as error:
                try:
                    await self.runBluezGatttoolFallback(error.address, stopEvent)
                except Exception as fallbackError:  # noqa: BLE001 - reconnect after compatibility backend failures
                    self.transition(ConnectionState.backoff, error=repr(fallbackError), retry=retryCount, delay=f"{retryDelay:.0f}s")
            except Exception as error:  # noqa: BLE001 - reconnect after backend-specific BLE failures
                self.transition(ConnectionState.backoff, error=repr(error), retry=retryCount, delay=f"{retryDelay:.0f}s")
            finally:
                self.metrics.endConnection()
                self.currentClient = None
                if worker:
                    worker.cancel()
                    await asyncio.gather(worker, return_exceptions=True)
                self.decoder.reset()
                self.disconnectHandler()
            if stopEvent.is_set(): break
            self.metrics.reconnects += 1
            try: await asyncio.wait_for(stopEvent.wait(), timeout=retryDelay)
            except asyncio.TimeoutError: pass
            retryDelay, retryCount = min(retryDelay * 2.0, 20.0), retryCount + 1
        self.transition(ConnectionState.stopped)
