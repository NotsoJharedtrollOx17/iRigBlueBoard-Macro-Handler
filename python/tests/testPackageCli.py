import json
import tempfile
import unittest
from pathlib import Path

from blueboard_macro_handler.ble_midi import encodeBleMidi
from blueboard_macro_handler.cli import loadReplayPackets, main


class PackageCliTests(unittest.TestCase):
    def testReplayFixtureLoads(self) -> None:
        packets = loadReplayPackets(Path(__file__).parent / "fixtures" / "blueboardPackets.json")
        self.assertEqual(len(packets), 8)
        self.assertEqual(packets[0], bytes.fromhex("80 80 B0 14 7F"))

    def testValidateDefaultConfig(self) -> None:
        self.assertEqual(main(["validate"]), 0)

    def testInvalidReplayReturnsError(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as value:
            json.dump({"packets": ["invalid"]}, value)
        path = Path(value.name)
        self.addCleanup(path.unlink, missing_ok=True)
        self.assertEqual(main(["replay", str(path)]), 2)

    def testOutboundEncoderProducesBleMidiFrame(self) -> None:
        packet = encodeBleMidi(0xB0, bytes((20, 127)), timestamp=0)
        self.assertEqual(packet, bytes.fromhex("80 80 B0 14 7F"))
