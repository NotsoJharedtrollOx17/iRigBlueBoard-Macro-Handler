from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from bleMidi import MidiEvent, MidiMessageType

logger = logging.getLogger("router")


@dataclass(frozen=True)
class Binding:
    cc: int
    edge: str
    action: str


def loadBindings(path: Path) -> list[Binding]:
    with path.open(encoding="utf-8") as configFile:
        rawConfig = json.load(configFile)
    return [Binding(int(item["cc"]), item["edge"], item["action"]) for item in rawConfig["bindings"]]


class Router:
    def __init__(self, bindings: list[Binding]) -> None:
        self.bindings = bindings
        self.buttonState: dict[int, bool] = {}

    def handleEvent(self, event: MidiEvent) -> None:
        logger.info(
            "midi type=%s channel=%d data1=%d data2=%d",
            event.messageType.value,
            event.channel + 1,
            event.data1,
            event.data2,
        )
        if event.messageType is not MidiMessageType.controlChange or event.channel != 0:
            return

        pressed = event.data2 >= 64
        previous = self.buttonState.get(event.data1, False)
        self.buttonState[event.data1] = pressed
        if previous == pressed:
            return

        edge = "press" if pressed else "release"
        for binding in self.bindings:
            if binding.cc == event.data1 and binding.edge == edge:
                # Initial milestone intentionally logs actions instead of injecting input.
                logger.info("action=%s cc=%d edge=%s", binding.action, binding.cc, edge)

    def releaseAll(self) -> None:
        active = [cc for cc, pressed in self.buttonState.items() if pressed]
        self.buttonState.clear()
        if active:
            logger.warning("cleared active buttons after disconnect: %s", active)
