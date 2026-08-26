"""Gemini call that proposes {action, params, rationale}, constrained to
the case type's allowed action subset (PRD §9.1 step 1). The proposal is
never trusted directly - app/policy/guardrails.py validates it before
anything is allowed to execute.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from google.genai import errors

from app.config import settings
from app.detection.gemini_client import get_client
from app.llm_resilience import call_with_resilience

# Fail-safe when the LLM output can't be parsed/trusted: escalate to a
# human rather than silently doing nothing or guessing an action.
FALLBACK_PROPOSAL = {
    "action": "escalate_human",
    "params": {},
    "rationale": "LLM proposal was unparseable or invalid; failing safe to human escalation.",
}

PROMPT_TEMPLATE = """You are the policy engine for an Indian fintech revenue-recovery agent. Given a case, propose exactly one recovery action.

Case type: {case_type}
Root cause: {root_cause}
Amount: INR {amount}
Customer responsiveness profile: {responsiveness_profile}
Customer preferred channel: {preferred_channel}
Prior attempts on this case ({attempt_count}): {attempt_summary}

Allowed actions (pick exactly one): {allowed_actions}

Action param notes:
- retry_scheduled requires params.retry_date_offset_hours (int, hours from now)
- send_reminder requires params.tone ("gentle" or "firm")
- stop_case requires params.reason (string)
- other actions take no params (use {{}})

Respond with ONLY a JSON object, no markdown fences, in this exact shape:
{{"action": "<one of the allowed actions>", "params": {{...}}, "rationale": "<one sentence, why this action fits this case>"}}
"""


def _summarize_attempts(attempts: list) -> str:
    if not attempts:
        return "none yet"
    return "; ".join(f"{a.action} via {a.channel} -> {a.outcome}" for a in attempts)


def build_prompt(case, customer, attempts: list, allowed_actions: list[str]) -> str:
    return PROMPT_TEMPLATE.format(
        case_type=case.type,
        root_cause=case.root_cause,
        amount=case.amount,
        responsiveness_profile=customer.responsiveness_profile,
        preferred_channel=customer.preferred_channel,
        attempt_count=len(attempts),
        attempt_summary=_summarize_attempts(attempts),
        allowed_actions=", ".join(allowed_actions),
    )


def propose_action(
    case,
    customer,
    attempts: list,
    allowed_actions: list[str],
    client: Any = None,
    now: datetime | None = None,
) -> dict:
    """`now` should be the caller's notion of the current time (the batch
    runner's simulated clock in instant mode, real wall clock otherwise).
    It anchors any retry_date the LLM expresses as an offset so scheduled
    retries land on the same timeline the rest of the pipeline runs on -
    using wall clock here made LLM-chosen offsets land days in the past
    relative to an advanced sim clock.
    """
    client = client or get_client()
    prompt = build_prompt(case, customer, attempts, allowed_actions)
    try:
        response = call_with_resilience(
            lambda: client.models.generate_content(model=settings.gemini_model, contents=prompt)
        )
    except (errors.APIError, OSError):
        # Unrecoverable API/network errors fail safe exactly like an
        # unparseable proposal - a case never gets stuck because Gemini was
        # unreachable or rate-limited, it just escalates to a human instead.
        # Transient errors (429/5xx/timeouts) were already retried with
        # backoff by call_with_resilience before we get here.
        return dict(FALLBACK_PROPOSAL)
    return _parse_and_validate(response.text or "", allowed_actions, now=now)


def _parse_and_validate(text: str, allowed_actions: list[str], now: datetime | None = None) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return dict(FALLBACK_PROPOSAL)

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return dict(FALLBACK_PROPOSAL)

    action = data.get("action")
    if action not in allowed_actions:
        return dict(FALLBACK_PROPOSAL)

    params = data.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    if action == "retry_scheduled":
        params = _normalize_retry_params(params, now=now)

    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = "(no rationale provided by model)"

    return {"action": action, "params": params, "rationale": rationale}


def _normalize_retry_params(params: dict, now: datetime | None = None) -> dict:
    offset_hours = params.get("retry_date_offset_hours")
    try:
        offset_hours = float(offset_hours)
    except (TypeError, ValueError):
        offset_hours = 72.0  # PRD example: insufficient_funds retry 3+ days later
    retry_date = (now or datetime.now(timezone.utc)) + timedelta(hours=offset_hours)
    return {"retry_date": retry_date}
