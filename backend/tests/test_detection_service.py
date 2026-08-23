import uuid

from app.db.session import SessionLocal
from app.detection.service import detect_and_diagnose_case, run_detection_on_batch
from app.models import AuditEvent, Case, Customer
from tests.fakes import FakeGeminiClient


def _make_customer_and_case(db, case_type: str, raw_failure_reason: str | None) -> Case:
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
        type=case_type,
        customer_id=customer.id,
        amount=1000,
        currency="INR",
        status="open",
        raw_failure_reason=raw_failure_reason,
        root_cause=None,
        outcome="pending",
        recovered_amount=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_detect_and_diagnose_rule_path_writes_events_and_root_cause():
    db = SessionLocal()
    try:
        case = _make_customer_and_case(db, "payment_failure", "Decline code 51: insufficient funds")
        detect_and_diagnose_case(db, case)
        db.commit()

        assert case.root_cause == "insufficient_funds"

        events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).order_by(AuditEvent.timestamp).all()
        event_types = [e.event_type for e in events]
        assert event_types == ["detected", "diagnosed"]

        diagnosed = events[1]
        assert diagnosed.actor == "system"
        assert diagnosed.payload["source"] == "rule"
        assert diagnosed.payload["root_cause"] == "insufficient_funds"
    finally:
        db.close()


def test_detect_and_diagnose_llm_path_writes_events_and_root_cause():
    db = SessionLocal()
    try:
        case = _make_customer_and_case(db, "payment_failure", "Transaction could not be completed.")
        fake_client = FakeGeminiClient(response_text='{"root_cause": "issuer_declined", "confidence": 0.7}')
        detect_and_diagnose_case(db, case, llm_client=fake_client)
        db.commit()

        assert case.root_cause == "issuer_declined"
        assert len(fake_client.calls) == 1

        diagnosed = (
            db.query(AuditEvent)
            .filter(AuditEvent.case_id == case.id, AuditEvent.event_type == "diagnosed")
            .first()
        )
        assert diagnosed.actor == "llm"
        assert diagnosed.payload["source"] == "llm"
        assert diagnosed.payload["confidence"] == 0.7
    finally:
        db.close()


def test_detect_and_diagnose_skips_receivables():
    db = SessionLocal()
    try:
        case = _make_customer_and_case(db, "receivable", None)
        detect_and_diagnose_case(db, case)
        db.commit()

        assert case.root_cause is None
        events = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).all()
        assert events == []
    finally:
        db.close()


def test_run_detection_on_batch_only_processes_undiagnosed_payment_like_cases():
    db = SessionLocal()
    try:
        already_diagnosed = _make_customer_and_case(db, "payment_failure", "Card expired")
        already_diagnosed.root_cause = "card_expired"
        db.add(already_diagnosed)

        needs_rule = _make_customer_and_case(db, "mandate_failure", "Mandate revoked by customer")
        needs_llm = _make_customer_and_case(db, "payment_failure", "Generic decline, no code")
        receivable = _make_customer_and_case(db, "receivable", None)
        db.commit()

        fake_client = FakeGeminiClient(response_text='{"root_cause": "issuer_declined", "confidence": 0.5}')
        processed = run_detection_on_batch(db, llm_client=fake_client)
        processed_ids = {c.id for c in processed}

        assert already_diagnosed.id not in processed_ids
        assert receivable.id not in processed_ids
        assert needs_rule.id in processed_ids
        assert needs_llm.id in processed_ids

        db.refresh(needs_rule)
        db.refresh(needs_llm)
        assert needs_rule.root_cause == "mandate_revoked"
        assert needs_llm.root_cause == "issuer_declined"
    finally:
        db.close()
