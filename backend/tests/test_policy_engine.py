import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import AuditEvent, Case, Customer
from app.policy.engine import decide_action
from tests.fakes import FakeGeminiClient

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _make_case(db, case_type="payment_failure", root_cause="insufficient_funds", created_at=None, **customer_kwargs):
    customer = Customer(
        id=uuid.uuid4(),
        dnd_registered=customer_kwargs.get("dnd_registered", False),
        responsiveness_profile=customer_kwargs.get("responsiveness_profile", "cooperative"),
        preferred_channel=customer_kwargs.get("preferred_channel", "sms"),
        card_on_file_status="valid",
    )
    db.add(customer)
    case = Case(
        id=uuid.uuid4(),
        type=case_type,
        customer_id=customer.id,
        amount=1500,
        currency="INR",
        created_at=created_at or (NOW - timedelta(days=1)),
        status="open",
        raw_failure_reason="Decline code 51: insufficient funds",
        root_cause=root_cause,
        outcome="pending",
        recovered_amount=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    db.refresh(customer)
    return case, customer


def test_decide_action_stopping_rule_skips_llm_entirely():
    db = SessionLocal()
    try:
        case, customer = _make_case(db, root_cause="fraud_suspected")
        client = FakeGeminiClient(response_text="should never be called")

        decision = decide_action(db, case, customer, [], now=NOW, llm_client=client)
        db.commit()

        assert decision["action"] == "escalate_human"
        assert decision["source"] == "stopping_rule"
        assert decision["rule"] == "fraud_or_dispute_auto_escalate"
        assert len(client.calls) == 0  # LLM never invoked

        events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).all()
        assert len(events) == 1
        assert events[0].event_type == "escalated"
    finally:
        db.close()


def test_decide_action_llm_proposal_passes_compliance():
    db = SessionLocal()
    try:
        case, customer = _make_case(db, root_cause="insufficient_funds", dnd_registered=False)
        client = FakeGeminiClient(
            response_text='{"action": "send_reminder", "params": {"tone": "gentle"}, "rationale": "gentle nudge"}'
        )

        decision = decide_action(db, case, customer, [], now=NOW, llm_client=client)
        db.commit()

        assert decision["action"] == "send_reminder"
        assert decision["source"] == "llm"
        assert decision["substituted"] is False

        events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.timestamp).all()
        event_types = [e.event_type for e in events]
        assert event_types == ["action_proposed", "compliance_check"]
        assert events[0].payload["action"] == "send_reminder"
        assert events[1].payload["passed"] is True
    finally:
        db.close()


def test_decide_action_dnd_substitution_logged():
    db = SessionLocal()
    try:
        case, customer = _make_case(db, case_type="receivable", root_cause="overdue_late", dnd_registered=True)
        client = FakeGeminiClient(response_text='{"action": "voice_call", "params": {}, "rationale": "escalate to voice"}')

        decision = decide_action(db, case, customer, [], now=NOW, llm_client=client)
        db.commit()

        assert decision["action"] == "send_reminder"
        assert decision["substituted"] is True
        assert decision["rule"] == "dnd_respected"

        compliance_event = (
            db.query(AuditEvent)
            .filter(AuditEvent.case_id == case.id, AuditEvent.event_type == "compliance_check")
            .first()
        )
        assert compliance_event.payload["proposed_action"] == "voice_call"
        assert compliance_event.payload["final_action"] == "send_reminder"
        assert compliance_event.payload["substituted"] is True
    finally:
        db.close()
