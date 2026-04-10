"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Render application logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "traveltom-api"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        trace_id = getattr(record, "trace_id", None)
        if isinstance(trace_id, str) and trace_id:
            payload["trace_id"] = trace_id

        span_id = getattr(record, "span_id", None)
        if isinstance(span_id, str) and span_id:
            payload["span_id"] = span_id

        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            payload["context"] = context

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(*, service_name: str, json_logs: bool) -> None:
    """Configure the root logger once for the API process."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter: logging.Formatter
    if json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        return

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
