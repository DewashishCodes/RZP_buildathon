"""Unit tests for app/llm_resilience.py - retry/backoff/rate-limit behavior.
No network: uses fake send() callables and fabricated APIErrors.
"""
import pytest
from google.genai import errors as genai_errors

from app.config import settings
from app.llm_resilience import _TokenBucket, call_with_resilience
from app.llm_resilience import reset_resilience_state, _get_bucket
from tests.fakes import FakeAPIError


def _coded_api_error(code: int) -> genai_errors.APIError:
    """Builds a real APIError instance carrying an HTTP code without needing
    to fabricate a requests.Response (FakeAPIError can't carry a code at all,
    which is exactly what its 'not retryable' classification depends on)."""
    err = genai_errors.APIError.__new__(genai_errors.APIError)
    err.code = code
    err.status = "FAKE"
    err.message = f"{code} (fake)"
    return err


def test_rate_limit_429_is_retried_then_succeeds(monkeypatch):
    # Non-zero base so backoff growth is deterministic even though conftest
    # zeroes it for speed: waits become base*1 + jitter[0,0.5) then base*2 +
    # jitter[0,0.5), which are strictly ordered.
    monkeypatch.setattr(settings, "llm_backoff_base_seconds", 1.0)
    calls = {"n": 0}
    sleeps: list[float] = []

    def flaky_then_ok():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _coded_api_error(429)
        return "ok"

    result = call_with_resilience(flaky_then_ok, sleep=sleeps.append)
    assert result == "ok"
    assert calls["n"] == 3
    # Exponential backoff: the second retry waits longer than the first.
    assert sleeps[0] < sleeps[1]


def test_attempts_exhausted_raises_last_error():
    def always_429():
        raise _coded_api_error(429)

    with pytest.raises(genai_errors.APIError):
        call_with_resilience(always_429, sleep=lambda _: None)


def test_non_retryable_client_error_fails_immediately():
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise _coded_api_error(400)

    with pytest.raises(genai_errors.APIError):
        call_with_resilience(bad_request, sleep=lambda _: None)
    assert calls["n"] == 1


def test_uncoded_api_error_not_retried():
    """Test-fake-shaped APIErrors (no .code) must fail through instantly so
    existing fallback-behavior tests keep seeing exactly one call."""
    calls = {"n": 0}

    def uncoded():
        calls["n"] += 1
        raise FakeAPIError()

    with pytest.raises(FakeAPIError):
        call_with_resilience(uncoded, sleep=lambda _: None)
    assert calls["n"] == 1


def test_transport_oserror_is_retried():
    calls = {"n": 0}

    def connection_reset():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionResetError("reset by peer")
        return "ok"

    assert call_with_resilience(connection_reset, sleep=lambda _: None) == "ok"
    assert calls["n"] == 2


def test_retry_after_header_extends_backoff():
    err = _coded_api_error(429)
    err.response = type("R", (), {"headers": {"Retry-After": "30"}})()
    sleeps: list[float] = []

    def always_429():
        raise err

    with pytest.raises(genai_errors.APIError):
        call_with_resilience(always_429, sleep=sleeps.append)
    # Both waits must cover the server's 30s window (+1s buffer), not just
    # the default backoff curve.
    assert all(s >= 31.0 for s in sleeps)


def test_retry_after_ignored_when_absent():
    err = _coded_api_error(429)  # no .response attribute at all
    sleeps: list[float] = []
    monkeypatch_backoff(2.0)

    def always_429():
        raise err

    try:
        with pytest.raises(genai_errors.APIError):
            call_with_resilience(always_429, sleep=sleeps.append)
        assert all(s < 5.0 for s in sleeps)
    finally:
        monkeypatch_backoff(0.0)


def monkeypatch_backoff(value: float) -> None:
    settings.llm_backoff_base_seconds = value


def test_rate_limiter_disabled_when_rpm_zero(monkeypatch):
    monkeypatch.setattr(settings, "llm_requests_per_minute", 0)
    reset_resilience_state()
    try:
        assert _get_bucket() is None
    finally:
        reset_resilience_state()


def test_token_bucket_paces_when_drained():
    bucket = _TokenBucket(requests_per_minute=60)
    for _ in range(60):  # drain the full capacity; each acquire returns instantly
        bucket.acquire()
    # Bucket empty: next acquire blocks until ~1 token refills (~1/sec at
    # 60rpm). It must succeed rather than error or loop forever; costs ~1s.
    bucket.acquire()