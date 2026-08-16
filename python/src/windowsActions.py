"""Windows keyboard macro backend using the native SendInput API."""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Callable

logger = logging.getLogger("windowsActions")

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
ULONG_PTR = ctypes.c_size_t


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MouseInput(ctypes.Structure):
    # Included because INPUT is a native C union. On 64-bit Windows this is
    # larger than KEYBDINPUT and therefore determines sizeof(INPUT).
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [
        ("mi", MouseInput),
        ("ki", KeyboardInput),
        ("hi", HardwareInput),
    ]


class Input(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", InputUnion)]


KEYS = {"CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12, "R": ord("R"), "TAB": 0x09}
COMBOS = {"ctrlShiftR": ("CTRL", "SHIFT", "R"), "altTab": ("ALT", "TAB")}


def getSendInput() -> Callable | None:
    if not hasattr(ctypes, "WinDLL"):
        return None
    sendInput = ctypes.WinDLL("user32", use_last_error=True).SendInput
    sendInput.argtypes = (wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int)
    sendInput.restype = wintypes.UINT
    return sendInput


class WindowsActions:
    def __init__(self, sendInput: Callable | None = None) -> None:
        self.sendInput = sendInput if sendInput is not None else getSendInput()

    @staticmethod
    def buildInputs(action: str):
        keys = [KEYS[key] for key in COMBOS[action]]
        inputs = (Input * (len(keys) * 2))()
        for index, key in enumerate(keys):
            inputs[index].type = INPUT_KEYBOARD
            inputs[index].ki.wVk = key
        for index, key in enumerate(reversed(keys), len(keys)):
            inputs[index].type = INPUT_KEYBOARD
            inputs[index].ki.wVk = key
            inputs[index].ki.dwFlags = KEYEVENTF_KEYUP
        return inputs

    def invoke(self, action: str) -> None:
        if action not in COMBOS:
            logger.info("action=%s has no Windows macro mapping", action)
            return
        if self.sendInput is None:
            raise RuntimeError("Windows SendInput is unavailable on this platform")

        inputs = self.buildInputs(action)
        if hasattr(ctypes, "set_last_error"):
            ctypes.set_last_error(0)
        sent = self.sendInput(len(inputs), inputs, ctypes.sizeof(Input))
        if sent != len(inputs):
            error = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else 0
            raise OSError(error, f"SendInput sent {sent} of {len(inputs)} events")
