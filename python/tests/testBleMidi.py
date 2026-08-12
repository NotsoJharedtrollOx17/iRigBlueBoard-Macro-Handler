import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bleMidi import BleMidiDecoder, MidiMessageType


class BleMidiDecoderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.decoder = BleMidiDecoder(clock=lambda: 123.0)

    def testCcPressAndRelease(self) -> None:
        events = self.decoder.decode(bytes.fromhex("80 80 B0 14 7F 81 B0 14 00"))
        self.assertEqual([(event.data1, event.data2) for event in events], [(20, 127), (20, 0)])
        self.assertTrue(all(event.messageType is MidiMessageType.controlChange for event in events))

    def testAllBlueBoardButtonsWithRunningStatus(self) -> None:
        events = self.decoder.decode(bytes.fromhex("80 80 B0 14 7F 81 15 7F 82 16 7F 83 17 7F"))
        self.assertEqual([event.data1 for event in events], [20, 21, 22, 23])

    def testNoteOnVelocityZeroIsNoteOff(self) -> None:
        event = self.decoder.decode(bytes.fromhex("80 80 90 3C 00"))[0]
        self.assertIs(event.messageType, MidiMessageType.noteOff)

    def testMalformedHeaderIsIgnored(self) -> None:
        self.assertEqual(self.decoder.decode(bytes.fromhex("00 80 B0 14 7F")), [])

    def testPartialMessageContinuesInNextPacket(self) -> None:
        self.assertEqual(self.decoder.decode(bytes.fromhex("80 80 B0 14")), [])
        event = self.decoder.decode(bytes.fromhex("80 81 7F"))[0]
        self.assertEqual((event.data1, event.data2), (20, 127))

    def testResetClearsRunningAndPartialState(self) -> None:
        self.decoder.decode(bytes.fromhex("80 80 B0 14"))
        self.decoder.reset()
        self.assertEqual(self.decoder.decode(bytes.fromhex("80 81 7F")), [])


if __name__ == "__main__":
    unittest.main()
