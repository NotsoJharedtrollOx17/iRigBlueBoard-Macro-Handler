from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .ble_midi import encodeBleMidi
from .models import RunMetrics

logger = logging.getLogger("blueboard.ledFeedback")

blueBoardButtonCcs = (20, 21, 22, 23)
PacketWriter = Callable[[bytes, bool], Awaitable[None]]


class LedFeedbackController:
    def __init__(self, metrics: RunMetrics | None = None, queueSize: int = 1024) -> None:
        if queueSize < len(blueBoardButtonCcs):
            raise ValueError(f"LED feedback queue must hold at least {len(blueBoardButtonCcs)} requests")
        self.metrics = metrics or RunMetrics()
        self.queue: asyncio.Queue[tuple[int, bool]] = asyncio.Queue(maxsize=queueSize)
        self.writer: PacketWriter | None = None
        self.worker: asyncio.Task | None = None
        self.requestedState: dict[int, bool] = {}

    async def bind(self, writer: PacketWriter) -> None:
        await self.unbind()
        self.writer = writer
        self.worker = asyncio.create_task(self.consume(), name="blueboard-led-feedback")
        for cc in blueBoardButtonCcs:
            self.setLed(cc, False, force=True)
        await self.flush()
        logger.info("LED feedback enabled; initialized buttons A-D off")

    async def unbind(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        self.worker = None
        self.writer = None
        self.requestedState.clear()
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()

    def setLed(self, cc: int, isOn: bool, *, force: bool = False) -> bool:
        if cc not in blueBoardButtonCcs:
            raise ValueError(f"unsupported BlueBoard LED CC: {cc}")
        if self.writer is None:
            return False
        if not force and self.requestedState.get(cc) == isOn:
            return False
        try:
            self.queue.put_nowait((cc, isOn))
        except asyncio.QueueFull:
            self.metrics.ledFeedbackDrops += 1
            logger.error("LED feedback queue full; button CC%d state=%s dropped", cc, "on" if isOn else "off")
            return False
        self.requestedState[cc] = isOn
        return True

    async def flush(self) -> None:
        await self.queue.join()

    async def consume(self) -> None:
        while True:
            cc, isOn = await self.queue.get()
            try:
                if self.writer is None:
                    continue
                packet = encodeBleMidi(0xB0, bytes((cc, 127 if isOn else 0)))
                await self.writer(packet, False)
                self.metrics.ledFeedbackWrites += 1
                logger.debug("button=%s cc=%d LED=%s", chr(ord("A") + cc - 20), cc, "on" if isOn else "off")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.ledFeedbackFailures += 1
                logger.exception("button CC%d LED feedback write failed", cc)
            finally:
                self.queue.task_done()
