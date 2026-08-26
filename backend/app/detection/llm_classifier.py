"""Gemini-backed root-cause classifier for free-text/ambiguous failure
messages that the deterministic rules (app/detection/rules.py) can't map.
Identical failure messages recur constantly within a batch, so results for
real (non-injected) client calls are memoized on the raw message - one
batch of 200 cases typically contains far fewer distinct messages than
cases, and this is the single cheapest LLM-cost win available.
"""
import json
import re
from functools import lru_cache
from typing import Any

from google.genai import errors

from app.config import settings
from app.constants import PAYMENT_ROOT_CAUSES
from app.detection.gemini_client import get_client

PROMPT_TEMPLATE = """You are classifying the root cause of a failed payment for an Indian fintech revenue-recovery system.

Failure message: "{message}"

Pick exactly one root cause from this list: {root_causes}

Respond with ONLY a JSON object, no markdown fences, in this exact shape:
{{"root_cause": "<one value from the list>", "confidence": <float between 0 and 1>}}
"""

# Fail-safe when the LLM output can't be parsed or trusted: issuer_declined
# maps to "single retry then escalate channel" per PRD §7 — a safe default
# for an unclear failure that won't self-resolve either way.
FALLBACK_ROOT_CAUSE = "issuer_declined"


def classify_by_llm(raw_failure_reason: str, client: Any = None) -> dict:
    """Cached when called with the real singleton client (production path);
    explicit clients (tests, demo scripts forcing specific responses) always
    bypass the cache so injected responses can't cross-contaminate."""
    if client is None:
        return _classify_cached(raw_failure_reason)
    return _classify_uncached(raw_failure_reason, client)


@lru_cache(maxsize=2048)
def _classify_cached(raw_failure_reason: str) -> dict:
    return _classify_uncached(raw_failure_reason, None)


def clear_classification_cache() -> None:
    _classify_cached.cache_clear()


def _classify_uncached(raw_failure_reason: str, client: Any) -> dict:
    client = client or get_client()
    prompt = PROMPT_TEMPLATE.format(
        message=raw_failure_reason,
        root_causes=", ".join(PAYMENT_ROOT_CAUSES),
    )
    try:
        response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
    except errors.APIError:
        # Network/quota/5xx errors fail safe exactly like unparseable output -
        # a case never gets stuck because Gemini was unreachable or rate-limited.
        return {"root_cause": FALLBACK_ROOT_CAUSE, "confidence": 0.0}
    return _parse_response(response.text or "")


def _parse_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"root_cause": FALLBACK_ROOT_CAUSE, "confidence": 0.0}

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"root_cause": FALLBACK_ROOT_CAUSE, "confidence": 0.0}

    root_cause = data.get("root_cause")
    if root_cause not in PAYMENT_ROOT_CAUSES:
        return {"root_cause": FALLBACK_ROOT_CAUSE, "confidence": 0.0}

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    return {"root_cause": root_cause, "confidence": confidence}
