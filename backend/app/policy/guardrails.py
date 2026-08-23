"""Stopping rules + compliance rules (PRD §9.2-9.3), deliberately kept as
pure, deterministic functions with no DB/LLM access. This is the piece the
PRD calls out as the demo-critical detail: guardrails are code, not prompt
instructions, so the LLM "agreeing" to a limit is never load-bearing.

Two layers, evaluated in order by app/policy/engine.py:

1. `check_stopping_rules` — absolute. If it fires, the case's fate is
   decided outright (escalate_human / stop_case) and the LLM proposal (if
   any) is discarded entirely.
2. `check_compliance` — substitutive. Runs only if no stopping rule fired.
   Takes the LLM's proposed action and either passes it through unchanged
   or swaps it for a compliant fallback, always returning a verdict.
"""
from datetime import datetime, timedelta, timezone

from app.policy.channels import determine_channel

MAX_RETRY_ATTEMPTS = 3
MAX_TOTAL_CONTACTS = 4
RETRY_MIN_SPACING = timedelta(hours=24)
SAME_CHANNEL_COOLDOWN = timedelta(hours=24)
CASE_AGE_ESCALATION_DAYS = 14
PRE_DEBIT_NOTICE_WINDOW = timedelta(hours=24)
CALLING_HOURS_START_IST = 9
CALLING_HOURS_END_IST = 19
IST = timezone(timedelta(hours=5, minutes=30))

RETRY_ACTIONS = {"retry_now", "retry_scheduled"}
COMPLIANT_FALLBACK_ACTION = "send_reminder"

AUTO_ESCALATE_ROOT_CAUSES = {"fraud_suspected", "disputed"}


def check_stopping_rules(case, customer, attempts: list, now: datetime | None = None) -> dict | None:
    """Returns a forced decision dict if a stopping rule fires, else None."""
    now = now or datetime.now(timezone.utc)

    if case.root_cause in AUTO_ESCALATE_ROOT_CAUSES:
        return {
            "action": "escalate_human",
            "params": {},
            "rule": "fraud_or_dispute_auto_escalate",
            "reason": f"root_cause={case.root_cause} requires immediate human escalation, no auto retry/nudge",
        }

    if attempts and attempts[-1].outcome == "opt_out":
        return {
            "action": "stop_case",
            "params": {"reason": "customer_opted_out"},
            "rule": "opt_out_honored",
            "reason": "prior attempt outcome was opt_out; no further contact permitted",
        }

    if len(attempts) >= MAX_TOTAL_CONTACTS:
        return {
            "action": "escalate_human",
            "params": {},
            "rule": "max_total_contacts",
            "reason": f"{len(attempts)} contact attempts already made (max {MAX_TOTAL_CONTACTS})",
        }

    retry_attempts = [a for a in attempts if a.action in RETRY_ACTIONS]
    if len(retry_attempts) >= MAX_RETRY_ATTEMPTS:
        return {
            "action": "escalate_human",
            "params": {},
            "rule": "max_retry_attempts",
            "reason": f"{len(retry_attempts)} retry attempts already made (max {MAX_RETRY_ATTEMPTS})",
        }

    case_created_at = case.created_at
    if case_created_at is not None:
        if case_created_at.tzinfo is None:
            case_created_at = case_created_at.replace(tzinfo=timezone.utc)
        case_age_days = (now - case_created_at).days
        if case_age_days >= CASE_AGE_ESCALATION_DAYS:
            return {
                "action": "escalate_human",
                "params": {},
                "rule": "case_age_exceeded",
                "reason": f"case open for {case_age_days} days (max {CASE_AGE_ESCALATION_DAYS})",
            }

    return None


def check_compliance(
    proposed_action: str,
    proposed_params: dict,
    case,
    customer,
    attempts: list,
    now: datetime | None = None,
) -> dict:
    """Always returns a verdict dict:
    {passed, action, params, rule, reason, substituted}
    """
    now = now or datetime.now(timezone.utc)
    action = proposed_action
    params = dict(proposed_params or {})

    if action in RETRY_ACTIONS:
        # Retries share a channel (silent_retry), so this rule takes priority
        # over the generic same-channel cooldown below - it's the more
        # specific, more informative rule name for this exact scenario.
        last_retry = next((a for a in reversed(attempts) if a.action in RETRY_ACTIONS), None)
        if last_retry is not None and (now - _aware(last_retry.timestamp)) < RETRY_MIN_SPACING:
            return _substitute(action, "retry_spacing_24h", "last retry was less than 24h ago")
    else:
        proposed_channel = determine_channel(action, customer.preferred_channel)
        if proposed_channel is not None:
            for attempt in reversed(attempts):
                if attempt.channel == proposed_channel and (now - _aware(attempt.timestamp)) < SAME_CHANNEL_COOLDOWN:
                    return _substitute(action, "same_channel_24h_cooldown", f"channel '{proposed_channel}' already contacted within 24h")

    if action == "voice_call" and getattr(customer, "dnd_registered", False):
        return _substitute(action, "dnd_respected", "customer is DND registered; voice_call not permitted")

    if action == "voice_call" and not _within_calling_hours(now):
        return _substitute(action, "calling_hours", f"voice_call only permitted {CALLING_HOURS_START_IST}:00-{CALLING_HOURS_END_IST}:00 IST")

    if action == "retry_scheduled":
        retry_date = params.get("retry_date")
        if retry_date is not None and retry_date.tzinfo is None:
            retry_date = retry_date.replace(tzinfo=timezone.utc)
        if retry_date is None or (retry_date - now) < PRE_DEBIT_NOTICE_WINDOW:
            corrected = now + PRE_DEBIT_NOTICE_WINDOW
            params["retry_date"] = corrected
            return {
                "passed": False,
                "action": action,
                "params": params,
                "rule": "pre_debit_notice_window",
                "reason": "retry_date adjusted so a pre-debit notification can be sent >=24h in advance",
                "substituted": True,
            }

    if attempts and attempts[-1].outcome == "opt_out" and action not in ("no_action", "stop_case"):
        return _substitute(action, "opt_out_honored", "prior attempt outcome was opt_out; no further contact permitted")

    return {"passed": True, "action": action, "params": params, "rule": None, "reason": None, "substituted": False}


def _substitute(action: str, rule: str, reason: str) -> dict:
    fallback = COMPLIANT_FALLBACK_ACTION if action != COMPLIANT_FALLBACK_ACTION else "no_action"
    return {"passed": False, "action": fallback, "params": {}, "rule": rule, "reason": reason, "substituted": True}


def _within_calling_hours(now_utc: datetime) -> bool:
    now_ist = now_utc.astimezone(IST)
    return CALLING_HOURS_START_IST <= now_ist.hour < CALLING_HOURS_END_IST


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
