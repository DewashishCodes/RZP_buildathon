"""Tests for the dashboard extras backed by rollup.py: the guardrail
intervention feed and the cumulative recovery curve."""
import uuid
from datetime import datetime, timezone

import pytest

from app.audit.rollup import guardrail_interventions, recovery_curve
from app.db.session import SessionLocal
from app.execution.runner import run_batch
from app.models import Attempt, AuditEvent, Case, Customer
from app.simulation.merchants import seed_merchants
from tests.fakes import FakeGeminiClient


NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
BATCH_ID = uuid.uuid4()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_case(db, *, case_type="payment_failure", root_cause=None, amount=100.0, recovered_amount=0.0, status="open"):
    merchant = seed_merchants(db)[0]
    customer = Customer(
        dnd_registered=False, responsiveness_profile="cooperative", preferred_channel="sms", card_on_file_status="valid"
    )
    db.add(customer)
    db.flush()
    case = Case(
        type=case_type,
        customer_id=customer.id,
        amount=amount,
        recovered_amount=recovered_amount,
        status=status,
        outcome="pending",
        disputed=False,
        root_cause=root_cause,
        batch_id=BATCH_ID,
        merchant_id=merchant.id,
    )
    db.add(case)
    db.flush()
    return case


def test_guardrail_feed_lists_stopping_rule_events_with_rule_and_case(db):
    fraud_case = _make_case(db, root_cause="fraud_suspected", amount=5000)

    # Fraud auto-escalates via the pure stopping rule - no LLM involved.
    run_batch(db, now=NOW, case_ids=[fraud_case.id], llm_client=FakeGeminiClient())

    feed = guardrail_interventions(db, batch_id=BATCH_ID)

    assert len(feed) >= 1
    stopping = [i for i in feed if i["kind"] == "stopping_rule"]
    assert len(stopping) == 1
    assert stopping[0]["rule"] == "fraud_or_dispute_auto_escalate"
    assert stopping[0]["case_id"] == str(fraud_case.id)
    assert stopping[0]["reason"]
    assert stopping[0]["timestamp"] is not None


def test_guardrail_feed_includes_compliance_substitutions(db):
    case = _make_case(db, root_cause="overdue_mid", amount=3000)
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            case_id=case.id,
            event_type="compliance_check",
            actor="system",
            payload={"passed": False, "substituted": True, "rule": "dnd_respect", "reason": "DND blocks voice_call"},
        )
    )
    db.commit()

    feed = guardrail_interventions(db, batch_id=BATCH_ID)

    subs = [i for i in feed if i["kind"] == "compliance_substitution"]
    assert len(subs) == 1
    assert subs[0]["rule"] == "dnd_respect"


def test_guardrail_feed_404_scoping_excludes_other_batches(db):
    case = _make_case(db, root_cause="fraud_suspected")
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            case_id=case.id,
            event_type="escalated",
            actor="system",
            payload={"rule": "x", "reason": "y"},
        )
    )
    db.commit()

    assert guardrail_interventions(db, batch_id=uuid.uuid4()) == []


def test_recovery_curve_accumulates_recovered_cases_in_time_order(db):
    case_a = _make_case(db, amount=4000, recovered_amount=4000, status="recovered", root_cause="issuer_declined")
    case_b = _make_case(db, amount=2500, recovered_amount=2500, status="recovered", root_cause="bank_timeout")

    for ts in (NOW, datetime(2026, 8, 25, 13, 0, 0, tzinfo=timezone.utc)):
        pass

    db.add(
        AuditEvent(
            id=uuid.uuid4(), case_id=case_a.id, event_type="outcome_recorded",
            actor="system", payload={"outcome": "success"}, timestamp=NOW,
        )
    )
    later = datetime(2026, 8, 25, 13, 0, 0, tzinfo=timezone.utc)
    db.add(
        AuditEvent(
            id=uuid.uuid4(), case_id=case_b.id, event_type="outcome_recorded",
            actor="system", payload={"outcome": "success"}, timestamp=later,
        )
    )
    # A non-recovery event on the same case must not double-count.
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            case_id=case_a.id,
            event_type="action_executed",
            actor="system",
            payload={},
            timestamp=NOW,
        )
    )
    db.commit()

    curve = recovery_curve(db, batch_id=BATCH_ID)

    assert [p["cumulative_recovered"] for p in curve] == [4000.0, 6500.0]
    assert curve[-1]["timestamp"] == later.isoformat()


def test_recovery_curve_empty_when_nothing_recovered(db):
    # Fresh batch id: earlier tests in this module recovered cases under
    # the shared BATCH_ID, so reuse would not be empty.
    fresh = uuid.uuid4()
    case = _make_case(db, amount=9000, status="escalated_human", root_cause="fraud_suspected")
    case.batch_id = fresh
    db.commit()
    assert recovery_curve(db, batch_id=fresh) == []
