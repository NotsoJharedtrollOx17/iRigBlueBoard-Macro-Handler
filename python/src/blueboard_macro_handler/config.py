from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ActionSpec:
    type: str
    keys: tuple[str, ...] = ()
    message: str = ""
    host: str = "127.0.0.1"
    port: int = 0
    program: str = ""
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Binding:
    cc: int
    edge: str
    action: ActionSpec | None
    channel: int = 1
    cooldownMs: int = 0


@dataclass(frozen=True)
class AppConfig:
    bindings: tuple[Binding, ...]
    name: str = "BlueBoard"
    scanTimeout: float = 8.0
    pair: bool = False


legacyActions = {
    "ctrlShiftR": ActionSpec("keyboard", keys=("CTRL", "SHIFT", "R")),
    "altTab": ActionSpec("keyboard", keys=("ALT", "TAB")),
}


def _requireObject(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a JSON object")
    return value


def parseAction(value: Any, context: str) -> ActionSpec | None:
    if value is None:
        return None
    if isinstance(value, str):
        return legacyActions.get(value, ActionSpec("log", message=value))
    raw = _requireObject(value, context)
    actionType = raw.get("type")
    if actionType not in {"keyboard", "log", "udp", "launch"}:
        raise ConfigError(f"{context}.type must be keyboard, log, udp, or launch")
    if actionType == "keyboard":
        keys = raw.get("keys")
        if not isinstance(keys, list) or not keys or not all(isinstance(key, str) for key in keys):
            raise ConfigError(f"{context}.keys must be a non-empty string array")
        return ActionSpec(actionType, keys=tuple(key.upper() for key in keys))
    if actionType == "udp":
        host, port = raw.get("host", "127.0.0.1"), raw.get("port")
        if not isinstance(host, str) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ConfigError(f"{context} requires a host and port from 1 to 65535")
        return ActionSpec(actionType, message=str(raw.get("message", "")), host=host, port=port)
    if actionType == "launch":
        program, args = raw.get("program"), raw.get("args", [])
        if not isinstance(program, str) or not program or not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ConfigError(f"{context} requires program and an optional string args array")
        return ActionSpec(actionType, program=program, args=tuple(args))
    return ActionSpec(actionType, message=str(raw.get("message", "")))


def loadConfig(path: Path) -> AppConfig:
    try:
        with path.open(encoding="utf-8") as configFile:
            root = _requireObject(json.load(configFile), "configuration")
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error

    rawBindings = root.get("bindings")
    if not isinstance(rawBindings, list):
        raise ConfigError("bindings must be an array")
    bindings: list[Binding] = []
    for index, value in enumerate(rawBindings):
        raw = _requireObject(value, f"bindings[{index}]")
        cc, edge = raw.get("cc"), raw.get("edge", "press")
        channel, cooldownMs = raw.get("channel", 1), raw.get("cooldownMs", 0)
        if not isinstance(cc, int) or not 0 <= cc <= 127:
            raise ConfigError(f"bindings[{index}].cc must be from 0 to 127")
        if edge not in {"press", "release"}:
            raise ConfigError(f"bindings[{index}].edge must be press or release")
        if not isinstance(channel, int) or not 1 <= channel <= 16:
            raise ConfigError(f"bindings[{index}].channel must be from 1 to 16")
        if not isinstance(cooldownMs, int) or cooldownMs < 0:
            raise ConfigError(f"bindings[{index}].cooldownMs cannot be negative")
        bindings.append(Binding(cc, edge, parseAction(raw.get("action"), f"bindings[{index}].action"), channel, cooldownMs))

    device = _requireObject(root.get("device", {}), "device")
    name, timeout, pair = device.get("name", "BlueBoard"), device.get("scanTimeout", 8.0), device.get("pair", False)
    if not isinstance(name, str) or not isinstance(timeout, (int, float)) or timeout <= 0 or not isinstance(pair, bool):
        raise ConfigError("device name, scanTimeout, or pair is invalid")
    return AppConfig(tuple(bindings), name=name, scanTimeout=float(timeout), pair=pair)


def configAsDict(config: AppConfig) -> dict[str, Any]:
    return {
        "device": {"name": config.name, "scanTimeout": config.scanTimeout, "pair": config.pair},
        "bindings": [
            {"cc": binding.cc, "channel": binding.channel, "edge": binding.edge, "cooldownMs": binding.cooldownMs, "action": None if binding.action is None else {"type": binding.action.type, "keys": list(binding.action.keys), "message": binding.action.message, "host": binding.action.host, "port": binding.action.port, "program": binding.action.program, "args": list(binding.action.args)}}
            for binding in config.bindings
        ],
    }
