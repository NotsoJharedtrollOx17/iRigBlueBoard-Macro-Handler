import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from windowsActions import INPUT_KEYBOARD, KEYEVENTF_KEYUP, KEYS, WindowsActions


class WindowsActionsTests(unittest.TestCase):
    def testCtrlShiftRBuildsPressThenReverseRelease(self) -> None:
        inputs = WindowsActions.buildInputs("ctrlShiftR")
        self.assertEqual(len(inputs), 6)
        self.assertEqual([item.ki.wVk for item in inputs], [KEYS["CTRL"], KEYS["SHIFT"], KEYS["R"], KEYS["R"], KEYS["SHIFT"], KEYS["CTRL"]])
        self.assertEqual([item.ki.dwFlags for item in inputs[:3]], [0, 0, 0])
        self.assertEqual([item.ki.dwFlags for item in inputs[3:]], [KEYEVENTF_KEYUP] * 3)
        self.assertTrue(all(item.type == INPUT_KEYBOARD for item in inputs))

    def testInvokePassesNativeInputSize(self) -> None:
        received = {}
        def fakeSendInput(count, inputs, inputSize):
            received.update(count=count, inputs=inputs, inputSize=inputSize)
            return count
        WindowsActions(sendInput=fakeSendInput).invoke("altTab")
        self.assertEqual(received["count"], 4)
        self.assertEqual(received["inputSize"], 40)
        self.assertEqual(received["inputs"][0].ki.wVk, KEYS["ALT"])

    def testUnknownActionDoesNotCallNativeApi(self) -> None:
        WindowsActions(sendInput=lambda *_: self.fail("must not execute")).invoke("unknown")


if __name__ == "__main__":
    unittest.main()
