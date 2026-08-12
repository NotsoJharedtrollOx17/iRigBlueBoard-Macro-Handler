from __future__ import annotations
import sys
def createActions(execute: bool):
    if not execute: return None
    if sys.platform == "win32":
        from windowsActions import WindowsActions
        return WindowsActions()
    if sys.platform.startswith("linux"):
        from linuxActions import LinuxActions
        return LinuxActions()
    raise RuntimeError(f"No keyboard backend for {sys.platform}")
