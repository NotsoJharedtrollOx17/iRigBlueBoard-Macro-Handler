from __future__ import annotations

import logging
from time import monotonic

from .actions import ActionDispatcher
from .config import AppConfig, Binding
from .models import MidiEvent, MidiMessageType, RunMetrics

logger = logging.getLogger("blueboard.router")


class Router:
    def __init__(self, config: AppConfig, actions: ActionDispatcher, metrics: RunMetrics | None = None) -> None:
        self.config, self.actions = config, actions
        self.metrics = metrics or RunMetrics()
        self.buttonState: dict[tuple[int, int], bool] = {}
        self.lastActionAt: dict[Binding, float] = {}

    def handleEvent(self, event: MidiEvent) -> None:
        self.metrics.events += 1
        logger.info("midi type=%s channel=%d data1=%d data2=%d", event.messageType.value, event.channel + 1, event.data1, event.data2)
        if event.messageType is not MidiMessageType.controlChange:
            return
        key, pressed = (event.channel, event.data1), event.data2 >= 64
        previous = self.buttonState.get(key, False)
        self.buttonState[key] = pressed
        if previous == pressed:
            return
        edge, now = ("press" if pressed else "release"), monotonic()
        for binding in self.config.bindings:
            if binding.cc != event.data1 or binding.channel - 1 != event.channel or binding.edge != edge or binding.action is None:
                continue
            lastAt = self.lastActionAt.get(binding, float("-inf"))
            if (now - lastAt) * 1000 < binding.cooldownMs:
                logger.warning("action suppressed by cooldown cc=%d", binding.cc)
                continue
            self.lastActionAt[binding] = now
            try:
                if self.actions.invoke(binding.action):
                    self.metrics.actions += 1
            except Exception:
                self.metrics.actionFailures += 1
                logger.exception("macro action failed cc=%d type=%s", binding.cc, binding.action.type)

    def releaseAll(self) -> None:
        active = [key for key, pressed in self.buttonState.items() if pressed]
        self.buttonState.clear()
        try:
            self.actions.releaseAll()
        except Exception:
            logger.exception("failed to release active keyboard state")
        if active:
            logger.warning("cleared active buttons after disconnect: %s", active)
