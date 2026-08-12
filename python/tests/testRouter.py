import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bleMidi import MidiEvent, MidiMessageType
from router import Binding, Router


class RouterTests(unittest.TestCase):
    def testPressAndReleaseUpdateState(self) -> None:
        router = Router([Binding(20, "press", "buttonA")])
        router.handleEvent(MidiEvent(MidiMessageType.controlChange, 0, 20, 127, 1.0))
        self.assertTrue(router.buttonState[20])
        router.handleEvent(MidiEvent(MidiMessageType.controlChange, 0, 20, 0, 2.0))
        self.assertFalse(router.buttonState[20])

    def testOtherChannelsAreIgnored(self) -> None:
        router = Router([])
        router.handleEvent(MidiEvent(MidiMessageType.controlChange, 1, 20, 127, 1.0))
        self.assertEqual(router.buttonState, {})

    def testReleaseAllClearsState(self) -> None:
        router = Router([])
        router.handleEvent(MidiEvent(MidiMessageType.controlChange, 0, 20, 127, 1.0))
        router.releaseAll()
        self.assertEqual(router.buttonState, {})


if __name__ == "__main__":
    unittest.main()
