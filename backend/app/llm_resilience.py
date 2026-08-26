"""Client-side pacing for Gemini calls: a shared token-bucket rate limiter.

Why this exists: Gemini free tiers enforce a requests-per-minute cap, and a
burst of policy/classifier calls across a batch trips it mid-run. Before
this module the only handling was the per-call fail-safe fallback
(escalate_human / issuer_declined), which silently converted rate-limited
cases into human escalations and deflated batch recovery numbers.
"""
import threading
import time

from app.config import settings


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
