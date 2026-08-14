import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from blueboard_macro_handler.client import BlueBoardClient, DiscoveredDevice, parseGatttoolNotification
from blueboard_macro_handler.models import RunMetrics
from blueboard_macro_handler.state import loadLastAddress, saveLastAddress


class FakeServices:
    def get_service(self, _uuid): return object()


class FakeBleakClient:
    instance = None
    def __init__(self, device, **_kwargs):
        self.device, self.services, self.is_connected = device, FakeServices(), True
        self.started = self.stopped = False
        FakeBleakClient.instance = self
    async def __aenter__(self): return self
    async def __aexit__(self, *_args): self.is_connected = False
    async def start_notify(self, _uuid, callback):
        self.started = True
        callback(None, bytearray.fromhex("80 80 B0 14 7F"))
        await asyncio.sleep(0.01)
    async def stop_notify(self, _uuid): self.stopped = True
    async def write_gatt_char(self, *_args, **_kwargs): pass


class PackageClientTests(unittest.IsolatedAsyncioTestCase):
    async def testConnectSubscribeConsumeAndStop(self) -> None:
        events, stopEvent, metrics = [], asyncio.Event(), RunMetrics()
        device = type("Device", (), {"address": "AA:BB"})()
        discovered = [DiscoveredDevice("iRig BlueBoard", "AA:BB", -50, device)]
        def receive(event): events.append(event); stopEvent.set()
        client = BlueBoardClient(receive, lambda: None, nameSubstring="BlueBoard", address=None, pair=False, scanTimeout=1, metrics=metrics)
        with patch("blueboard_macro_handler.client.discoverBlueBoards", AsyncMock(return_value=discovered)), patch("bleak.BleakClient", FakeBleakClient):
            await client.run(stopEvent)
        self.assertEqual(len(events), 1)
        self.assertTrue(FakeBleakClient.instance.started)
        self.assertTrue(FakeBleakClient.instance.stopped)
        self.assertEqual(metrics.packets, 1)

    async def testSavedAddressFallsBackToNameDiscovery(self) -> None:
        device = type("Device", (), {"address": "AA:BB"})()
        client = BlueBoardClient(lambda _: None, lambda: None, nameSubstring="BlueBoard", address="CC:DD", pair=False, scanTimeout=1)
        with patch("blueboard_macro_handler.client.discoverBlueBoards", AsyncMock(return_value=[DiscoveredDevice("iRig BlueBoard", "AA:BB", -50, device)])):
            self.assertIs(await client.findDevice(), device)

    def testStateRoundTrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            saveLastAddress(path, "AA:BB")
            self.assertEqual(loadLastAddress(path), "AA:BB")

    def testParsesGatttoolMidiNotification(self) -> None:
        line = "Notification handle = 0x0022 value: 80 80 b0 14 7f"
        self.assertEqual(parseGatttoolNotification(line), bytes.fromhex("80 80 b0 14 7f"))

    def testIgnoresOtherGatttoolOutput(self) -> None:
        self.assertIsNone(parseGatttoolNotification("Characteristic value was written successfully"))
        self.assertIsNone(parseGatttoolNotification("Notification handle = 0x001c value: 64"))
