"""Gemini-backed root-cause classifier for free-text/ambiguous failure
messages that the deterministic rules (app/detection/rules.py) can't map.
"""
import json
import re
from typing import Any

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
    client = client or get_client()
    prompt = PROMPT_TEMPLATE.format(
        message=raw_failure_reason,
        root_causes=", ".join(PAYMENT_ROOT_CAUSES),
    )
    response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
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
