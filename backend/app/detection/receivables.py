"""Deterministic root-cause classification for B2B receivables (PRD §7).
Unlike payment/mandate failures, this never needs an LLM: the overdue
bucket is a pure function of days elapsed since due_at, and disputes are
already a flag on the case (not something to infer from free text).
"""
from datetime import datetime, timezone

EARLY_MAX_DAYS = 15
MID_MAX_DAYS = 45


def classify_receivable(case, now: datetime | None = None) -> str:
    if case.disputed:
        return "disputed"

    now = now or datetime.now(timezone.utc)
    due_at = case.due_at
    if due_at is None:
        # Malformed data (a receivable should always have a due_at) - fail
        # safe to the most urgent bucket rather than crash detection.
        return "overdue_late"
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    days_overdue = (now - due_at).days

    if days_overdue <= EARLY_MAX_DAYS:
        return "overdue_early"
    if days_overdue <= MID_MAX_DAYS:
        return "overdue_mid"
    return "overdue_late"
