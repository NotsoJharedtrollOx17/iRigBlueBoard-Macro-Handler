from __future__ import annotations

import json
import logging
from time import monotonic


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "monotonic": round(monotonic(), 6),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configureLogging(debug: bool = False, jsonLogs: bool = False, logFile: str | None = None) -> None:
    level = logging.DEBUG if debug else logging.INFO
    formatter: logging.Formatter = JsonFormatter() if jsonLogs else logging.Formatter("%(relativeCreated)09.0fms %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if logFile:
        handlers.append(logging.FileHandler(logFile, encoding="utf-8"))
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)
