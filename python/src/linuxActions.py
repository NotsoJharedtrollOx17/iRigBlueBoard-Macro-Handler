from __future__ import annotations
import logging, os, struct, fcntl
logger = logging.getLogger("linuxActions")
UI_SET_EVBIT, UI_SET_KEYBIT, UI_DEV_CREATE, UI_DEV_DESTROY = 0x40045564, 0x40045565, 0x5501, 0x5502
EV_KEY, EV_SYN, SYN_REPORT = 1, 0, 0
KEY = {"CTRL": 29, "SHIFT": 42, "ALT": 56, "R": 19, "TAB": 15}
class LinuxActions:
    def __init__(self, devicePath: str = "/dev/uinput") -> None:
        self.device = os.open(devicePath, os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.device, UI_SET_EVBIT, EV_KEY)
        for key in KEY.values(): fcntl.ioctl(self.device, UI_SET_KEYBIT, key)
        os.write(self.device, struct.pack("80sHHH", b"BlueBoard Macro Handler", 3, 1, 1) + bytes(80))
        fcntl.ioctl(self.device, UI_DEV_CREATE)
    def _key(self, code: int, pressed: int) -> None: os.write(self.device, struct.pack("llHHI", 0, 0, EV_KEY, code, pressed))
    def invoke(self, action: str) -> None:
        combos = {"ctrlShiftR": ("CTRL", "SHIFT", "R"), "altTab": ("ALT", "TAB")}
        if action not in combos: logger.info("action=%s has no Linux macro mapping", action); return
        keys = [KEY[name] for name in combos[action]]
        for key in keys: self._key(key, 1)
        for key in reversed(keys): self._key(key, 0)
        os.write(self.device, struct.pack("llHHI", 0, 0, EV_SYN, SYN_REPORT, 0))
    def close(self) -> None:
        if getattr(self, "device", None) is not None: fcntl.ioctl(self.device, UI_DEV_DESTROY); os.close(self.device); self.device = None
    def __del__(self) -> None:
        try: self.close()
        except Exception: pass
