"""Client-side pacing and transient-error handling for every Gemini call:
a shared token-bucket rate limiter plus retry with exponential backoff.

Why this exists: Gemini free tiers enforce a requests-per-minute cap, and a
burst of policy/classifier calls across a batch trips it mid-run. Before
this module the only handling was the per-call fail-safe fallback
(escalate_human / issuer_declined), which silently converted rate-limited
cases into human escalations and deflated batch recovery numbers.

Retryable = HTTP 408/429/5xx APIErrors plus transport-level failures
(requests' ConnectionError/Timeout subclass OSError). Everything else -
bad key, malformed request, unknown error shapes like test fakes - fails
through immediately so callers' existing fail-safe fallbacks stay in charge.
"""
import random
import threading
import time

from google.genai import errors as genai_errors

from app.config import settings

_RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        # No code attribute (e.g. test fakes that never call super().__init__)
        # means we can't tell it was transient - don't retry it.
        return code in _RETRYABLE_CODES
    return isinstance(exc, OSError)


class _TokenBucket:
    """Thread-safe token bucket enforcing a client-side req/min cap, so we
    pace ourselves under the provider limit instead of discovering it via 429s."""

    def __init__(self, requests_per_minute: int):
        self.capacity = float(requests_per_minute)
        self._tokens = float(requests_per_minute)
        self._refill_per_second = requests_per_minute / 60.0
        self._updated_at = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._updated_at) * self._refill_per_second)
                self._updated_at = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            time.sleep(0.1)


_bucket: _TokenBucket | None = None


def _get_bucket() -> _TokenBucket | None:
    global _bucket
    rpm = settings.llm_requests_per_minute
    if rpm <= 0:
        # 0 disables pacing entirely (tests, or a paid tier without RPM caps).
        return None
    if _bucket is None or _bucket.capacity != rpm:
        _bucket = _TokenBucket(rpm)
    return _bucket


def reset_resilience_state() -> None:
    """Drops the rate-limiter bucket; used by tests after changing settings."""
    global _bucket
    _bucket = None


def _retry_after_seconds(exc: Exception) -> float | None:
    """Honors the server's Retry-After header on 429s when present - the
    free-tier per-minute window can outlast our default backoff curve, and
    the server knows exactly when it resets. Missing on fakes/errors that
    never carried a response; returns None there."""
    if not isinstance(exc, genai_errors.APIError):
        return None
    response = getattr(exc, "response", None)
    header = None
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers is not None:
            try:
                header = headers.get("Retry-After") or headers.get("retry-after")
            except Exception:  # noqa: BLE001 - header access is best-effort
                header = None
    if header is None:
        return None
    try:
        return max(float(header), 0.0)
    except (TypeError, ValueError):
        return None


def call_with_resilience(send, *, sleep=time.sleep):
    """Runs send() behind the shared rate limiter with retry/backoff on
    retryable errors. Raises the last exception once attempts are exhausted -
    callers keep their existing fail-safe fallback behavior.
    """
    max_attempts = max(settings.llm_max_attempts, 1)
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        bucket = _get_bucket()
        if bucket is not None:
            bucket.acquire()
        try:
            return send()
        except Exception as exc:  # noqa: BLE001 - classified by is_retryable
            if not is_retryable(exc):
                raise
            last_exc = exc
            if attempt < max_attempts - 1:
                backoff = settings.llm_backoff_base_seconds * (2**attempt) + random.uniform(0, 0.5)
                retry_after = _retry_after_seconds(exc)
                if retry_after is not None:
                    backoff = max(backoff, retry_after + 1.0)
                if backoff > 0:
                    sleep(backoff)
    assert last_exc is not None
    raise last_exc
