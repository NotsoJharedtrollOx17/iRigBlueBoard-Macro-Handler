from __future__ import annotations

import logging
import socket
import subprocess
import sys

from ..config import ActionSpec
from .base import KeyboardBackend

logger = logging.getLogger("blueboard.actions")


class ActionDispatcher:
    def __init__(self, execute: bool = False, keyboard: KeyboardBackend | None = None) -> None:
        self.execute = execute
        self.keyboard = keyboard

    def getKeyboard(self) -> KeyboardBackend:
        if self.keyboard is None:
            if sys.platform == "win32":
                from .windows import WindowsKeyboard
                self.keyboard = WindowsKeyboard()
            elif sys.platform.startswith("linux"):
                from .linux import LinuxKeyboard
                self.keyboard = LinuxKeyboard()
            else:
                raise RuntimeError(f"keyboard macros are unsupported on {sys.platform}")
        return self.keyboard

    def invoke(self, action: ActionSpec) -> bool:
        logger.info("action type=%s execute=%s", action.type, self.execute)
        if not self.execute or action.type == "log":
            if action.message:
                logger.info("action message=%s", action.message)
            return False
        if action.type == "keyboard":
            self.getKeyboard().sendCombo(action.keys)
        elif action.type == "udp":
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as datagram:
                datagram.sendto(action.message.encode("utf-8"), (action.host, action.port))
        elif action.type == "launch":
            subprocess.Popen([action.program, *action.args], shell=False)
        else:
            raise ValueError(f"unsupported action type: {action.type}")
        return True

    def releaseAll(self) -> None:
        if self.keyboard is not None:
            self.keyboard.releaseAll()

    def close(self) -> None:
        if self.keyboard is not None:
            self.keyboard.close()
