"""Structured JSON logging + a per-request request_id.

Plain-text logs are fine for a terminal but useless for a real deployment
- nothing to grep/filter/ship to a log aggregator by field. This makes
every log line one JSON object with a timestamp, level, logger name,
message, and (inside a request) the request_id that ties every log line
for that request together - and any `extra={...}` fields a caller passed
(app/api/webhooks.py and app/execution/providers.py already do this).

app.api.main wires RequestIDMiddleware in and calls configure_logging()
at import time.
"""
import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord carries regardless of what was logged - used
# to find the caller-supplied `extra` fields, which are just additional
# attributes bolted onto the record by logging.Logger.makeRecord.
_STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_ctx.get()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    # Idempotent: uvicorn --reload re-imports app.api.main on every reload,
    # which would otherwise stack a fresh handler on each reload.
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(level)


def new_request_id() -> str:
    return uuid.uuid4().hex
