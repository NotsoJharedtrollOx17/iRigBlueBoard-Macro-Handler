from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Callable


class MidiMessageType(Enum):
    controlChange = "controlChange"
    noteOn = "noteOn"
    noteOff = "noteOff"
    programChange = "programChange"
    pitchBend = "pitchBend"
    unknown = "unknown"


@dataclass(frozen=True)
class MidiEvent:
    messageType: MidiMessageType
    channel: int
    data1: int
    data2: int
    receivedAt: float


class BleMidiDecoder:
    """Stateful decoder for BLE-MIDI channel-voice messages."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self.clock = clock
        self.runningStatus: int | None = None
        self.pendingStatus: int | None = None
        self.pendingData = bytearray()

    def reset(self) -> None:
        self.runningStatus = None
        self.pendingStatus = None
        self.pendingData.clear()

    @staticmethod
    def dataLength(status: int) -> int | None:
        messageType = status & 0xF0
        if 0x80 <= messageType <= 0xB0 or messageType == 0xE0:
            return 2
        if messageType in (0xC0, 0xD0):
            return 1
        return None

    def makeEvent(self, status: int, data: bytearray) -> MidiEvent:
        messageType = status & 0xF0
        data2 = data[1] if len(data) == 2 else 0
        if messageType == 0xB0:
            eventType = MidiMessageType.controlChange
        elif messageType == 0x90 and data2 != 0:
            eventType = MidiMessageType.noteOn
        elif messageType in (0x80, 0x90):
            eventType = MidiMessageType.noteOff
        elif messageType == 0xC0:
            eventType = MidiMessageType.programChange
        elif messageType == 0xE0:
            eventType = MidiMessageType.pitchBend
        else:
            eventType = MidiMessageType.unknown
        return MidiEvent(eventType, status & 0x0F, data[0], data2, self.clock())

    def decode(self, packet: bytes) -> list[MidiEvent]:
        if not packet or packet[0] & 0x80 == 0:
            return []

        events: list[MidiEvent] = []
        index = 1
        needTimestamp = True
        while index < len(packet):
            if needTimestamp:
                if packet[index] & 0x80 == 0:
                    index += 1
                    continue
                index += 1
                needTimestamp = False
                if index >= len(packet):
                    break

            if self.pendingStatus is None:
                value = packet[index]
                if value & 0x80:
                    index += 1
                    length = self.dataLength(value)
                    if length is None:
                        self.runningStatus = None
                        needTimestamp = True
                        continue
                    self.pendingStatus = value
                    self.runningStatus = value
                elif self.runningStatus is not None:
                    self.pendingStatus = self.runningStatus
                else:
                    index += 1
                    needTimestamp = True
                    continue

            expected = self.dataLength(self.pendingStatus)
            if expected is None:
                self.pendingStatus = None
                self.pendingData.clear()
                needTimestamp = True
                continue

            while index < len(packet) and len(self.pendingData) < expected:
                value = packet[index]
                if value & 0x80:
                    # A fresh BLE timestamp may occur while a split MIDI message is pending.
                    index += 1
                    continue
                self.pendingData.append(value)
                index += 1

            if len(self.pendingData) == expected:
                events.append(self.makeEvent(self.pendingStatus, self.pendingData))
                self.pendingStatus = None
                self.pendingData.clear()
                needTimestamp = True

        return events


def decodeBleMidi(packet: bytes) -> list[MidiEvent]:
    return BleMidiDecoder().decode(packet)
