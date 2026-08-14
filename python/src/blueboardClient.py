from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

from bleMidi import BleMidiDecoder, MidiEvent

serviceUuid = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
midiCharacteristicUuid = "7772e5db-3868-4112-a1a9-f2669d106bf3"
logger = logging.getLogger("blueboard")


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
        raise RuntimeError("Bleak is not installed; run: py -m pip install -e . from the repository root") from error

    found: dict[str, DiscoveredDevice] = {}

    def detected(device, advertisementData) -> None:
        name = advertisementData.local_name or device.name
        advertisedServices = {value.lower() for value in advertisementData.service_uuids}
        nameMatches = bool(name and nameSubstring.casefold() in name.casefold())
        if nameMatches or serviceUuid in advertisedServices:
            found[device.address] = DiscoveredDevice(
                name, device.address, advertisementData.rssi, device
            )

    async with BleakScanner(detection_callback=detected):
        await asyncio.sleep(timeout)
    return sorted(found.values(), key=lambda item: item.name or "")


class BlueBoardClient:
    def __init__(
        self,
        eventHandler: Callable[[MidiEvent], None],
        disconnectHandler: Callable[[], None],
        *,
        nameSubstring: str,
        address: str | None,
        pair: bool,
        scanTimeout: float,
    ) -> None:
        self.eventHandler = eventHandler
        self.disconnectHandler = disconnectHandler
        self.nameSubstring = nameSubstring
        self.address = address
        self.pair = pair
        self.scanTimeout = scanTimeout
        self.decoder = BleMidiDecoder()

    async def findDevice(self):
        devices = await discoverBlueBoards(self.nameSubstring, self.scanTimeout)
        if self.address:
            devices = [item for item in devices if item.address.casefold() == self.address.casefold()]
        if not devices:
            raise RuntimeError("BlueBoard not found; hold C while powering it on")
        selected = devices[0]
        logger.info("discovered name=%s address=%s RSSI=%s", selected.name, selected.address, selected.rssi)
        return selected.device

    async def run(self) -> None:
        from bleak import BleakClient

        retryDelay = 1.0
        retryCount = 0
        while True:
            disconnected = asyncio.Event()
            eventQueue: asyncio.Queue[bytes] = asyncio.Queue()
            worker: asyncio.Task[None] | None = None
            try:
                logger.info("state=scanning retry=%d", retryCount)
                device = await self.findDevice()
                logger.info("state=connecting pair=%s", self.pair)

                def onDisconnected(_client) -> None:
                    disconnected.set()

                async with BleakClient(
                    device,
                    disconnected_callback=onDisconnected,
                    services=[serviceUuid],
                    pair=self.pair,
                    timeout=45.0 if self.pair else 30.0,
                ) as client:
                    logger.info("state=subscribing characteristic=%s", midiCharacteristicUuid)

                    def onNotification(_characteristic, data: bytearray) -> None:
                        eventQueue.put_nowait(bytes(data))

                    async def consumeNotifications() -> None:
                        while True:
                            packet = await eventQueue.get()
                            logger.debug("packet=%s", packet.hex(" "))
                            for event in self.decoder.decode(packet):
                                try:
                                    self.eventHandler(event)
                                except Exception:
                                    logger.exception("event handler failed; continuing notification loop")

                    worker = asyncio.create_task(consumeNotifications())
                    await client.start_notify(midiCharacteristicUuid, onNotification)
                    logger.info("state=connected address=%s", device.address)
                    retryDelay = 1.0
                    retryCount = 0
                    await disconnected.wait()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.error("state=backoff error=%r retry=%d delay=%.0fs", error, retryCount, retryDelay)
            finally:
                if worker is not None:
                    worker.cancel()
                    await asyncio.gather(worker, return_exceptions=True)
                self.decoder.reset()
                self.disconnectHandler()

            await asyncio.sleep(retryDelay)
            retryDelay = min(retryDelay * 2.0, 20.0)
            retryCount += 1
