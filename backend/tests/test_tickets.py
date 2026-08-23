import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.execution.tickets import create_ticket_for_case
from app.models import Case, Customer, Ticket

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _make_case(db, root_cause="insufficient_funds"):
    customer = Customer(
        id=uuid.uuid4(),
        dnd_registered=False,
        responsiveness_profile="cooperative",
        preferred_channel="sms",
        card_on_file_status="valid",
    )
    db.add(customer)
    case = Case(
        id=uuid.uuid4(),
        type="payment_failure",
        customer_id=customer.id,
        amount=5000,
        currency="INR",
        created_at=NOW,
        status="escalated_human",
        root_cause=root_cause,
        outcome="pending",
        recovered_amount=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_create_ticket_for_case_writes_a_ticket():
    db = SessionLocal()
    try:
        case = _make_case(db)
        ticket = create_ticket_for_case(db, case, rule="max_total_contacts", reason="hit the contact cap")
        db.commit()

        assert ticket.case_id == case.id
        assert ticket.status == "open"
        assert ticket.assignee == "Unassigned"
        assert "max_total_contacts" in ticket.reason or ticket.reason == "hit the contact cap"
    finally:
        db.close()


def test_create_ticket_is_idempotent_per_case():
    db = SessionLocal()
    try:
        case = _make_case(db)
        first = create_ticket_for_case(db, case, rule=None, reason=None)
        db.commit()
        second = create_ticket_for_case(db, case, rule=None, reason=None)
        db.commit()

        assert first.id == second.id
        count = db.scalar(select(func.count()).select_from(Ticket).where(Ticket.case_id == case.id))
        assert count == 1
    finally:
        db.close()


def test_fraud_dispute_rule_gets_urgent_priority():
    db = SessionLocal()
    try:
        case = _make_case(db, root_cause="fraud_suspected")
        ticket = create_ticket_for_case(db, case, rule="fraud_or_dispute_auto_escalate", reason="fraud")
        db.commit()

        assert ticket.priority == "urgent"
    finally:
        db.close()


def test_max_contacts_rule_gets_high_priority():
    db = SessionLocal()
    try:
        case = _make_case(db)
        ticket = create_ticket_for_case(db, case, rule="max_total_contacts", reason="exhausted")
        db.commit()

        assert ticket.priority == "high"
    finally:
        db.close()


def test_generic_escalation_gets_normal_priority():
    db = SessionLocal()
    try:
        case = _make_case(db)
        ticket = create_ticket_for_case(db, case, rule=None, reason="LLM chose to escalate")
        db.commit()

        assert ticket.priority == "normal"
    finally:
        db.close()
