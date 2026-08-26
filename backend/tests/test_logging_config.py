import json
import logging

from fastapi.testclient import TestClient

from app.api.main import app
from app.logging_config import JsonFormatter, request_id_ctx

client = TestClient(app)


def _make_record(msg="hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord(name="test.logger", level=logging.INFO, pathname=__file__, lineno=1, msg=msg, args=(), exc_info=None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_valid_json_with_expected_fields():
    formatter = JsonFormatter()
    record = _make_record("something happened", case_id="abc-123")

    line = formatter.format(record)
    parsed = json.loads(line)

    assert parsed["message"] == "something happened"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["case_id"] == "abc-123"
    assert "timestamp" in parsed


def test_json_formatter_includes_request_id_from_contextvar():
    formatter = JsonFormatter()
    token = request_id_ctx.set("req-xyz")
    try:
        line = formatter.format(_make_record())
    finally:
        request_id_ctx.reset(token)

    assert json.loads(line)["request_id"] == "req-xyz"


def test_json_formatter_omits_request_id_outside_a_request():
    formatter = JsonFormatter()
    assert request_id_ctx.get() is None
    line = formatter.format(_make_record())
    assert "request_id" not in json.loads(line)


def test_response_carries_a_request_id_header():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")


def test_response_echoes_an_inbound_request_id():
    resp = client.get("/health", headers={"X-Request-ID": "caller-supplied-id"})
    assert resp.headers.get("X-Request-ID") == "caller-supplied-id"
