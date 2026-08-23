"""Auto-creates a support ticket whenever a case escalates to a human -
the in-house mock support tool that gives escalate_human somewhere real
to land, instead of a dead-end status. Not an integration with a real
external ticketing product (see app/models.py:Ticket docstring).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Case, Ticket

# fraud/dispute cases and cases that exhausted every automated channel are
# more urgent than a routine "case is old, hand it off" escalation.
URGENT_RULES = {"fraud_or_dispute_auto_escalate"}
HIGH_PRIORITY_RULES = {"max_total_contacts", "max_retry_attempts", "max_rounds_safety_cap"}


def _priority_for(rule: str | None) -> str:
    if rule in URGENT_RULES:
        return "urgent"
    if rule in HIGH_PRIORITY_RULES:
        return "high"
    return "normal"


def _subject_for(case: Case, rule: str | None) -> str:
    cause = case.root_cause or "undiagnosed"
    if rule == "fraud_or_dispute_auto_escalate":
        return f"Suspected {cause} on Rs.{case.amount} case - needs manual review"
    if rule in HIGH_PRIORITY_RULES:
        return f"Automated recovery exhausted for {cause} case (Rs.{case.amount})"
    return f"{case.type.replace('_', ' ').title()} case escalated: {cause}"


def create_ticket_for_case(db: Session, case: Case, rule: str | None, reason: str | None) -> Ticket:
    """Idempotent: Ticket.case_id is unique, so calling this twice for the
    same case returns the existing ticket rather than erroring.
    """
    existing = db.execute(select(Ticket).where(Ticket.case_id == case.id)).scalar_one_or_none()
    if existing is not None:
        return existing

    ticket = Ticket(
        id=uuid.uuid4(),
        case_id=case.id,
        merchant_id=case.merchant_id,
        subject=_subject_for(case, rule),
        priority=_priority_for(rule),
        status="open",
        assignee="Unassigned",
        reason=reason or f"Escalated via rule: {rule}" if rule else "Escalated by the recovery agent",
    )
    db.add(ticket)
    return ticket
