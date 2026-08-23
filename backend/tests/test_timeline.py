import uuid
from datetime import datetime, timezone

from app.audit.timeline import get_case_timeline, list_cases
from app.db.session import SessionLocal
from app.execution.runner import run_batch
from app.models import Case, Customer
from tests.fakes import FakeGeminiClient

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _make_case(db, batch_id=None, raw_failure_reason="Decline code 59: suspected fraud", amount=1000):
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
        amount=amount,
        currency="INR",
        created_at=NOW,
        status="open",
        raw_failure_reason=raw_failure_reason,
        root_cause=None,
        outcome="pending",
        recovered_amount=0,
        batch_id=batch_id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_get_case_timeline_returns_none_for_unknown_case():
    db = SessionLocal()
    try:
        assert get_case_timeline(db, uuid.uuid4()) is None
    finally:
        db.close()


def test_get_case_timeline_is_chronological_with_no_gaps():
    db = SessionLocal()
    try:
        case = _make_case(db)
        run_batch(db, now=NOW, case_ids=[case.id])  # fraud -> stopping rule, no LLM needed

        timeline = get_case_timeline(db, case.id)

        assert timeline is not None
        assert timeline["case"].id == case.id
        event_types = [e.event_type for e in timeline["events"]]
        assert event_types == ["detected", "diagnosed", "escalated"]

        timestamps = [e.timestamp for e in timeline["events"]]
        assert timestamps == sorted(timestamps)
        assert len(set(timestamps)) == len(timestamps)
    finally:
        db.close()


def test_list_cases_filters_by_batch_id():
    db = SessionLocal()
    try:
        batch_id = uuid.uuid4()
        other_batch_id = uuid.uuid4()
        in_batch = _make_case(db, batch_id=batch_id)
        _make_case(db, batch_id=other_batch_id)

        results = list_cases(db, batch_id=batch_id)

        assert len(results) == 1
        assert results[0].id == in_batch.id
    finally:
        db.close()


def test_list_cases_filters_by_status_and_type():
    db = SessionLocal()
    try:
        batch_id = uuid.uuid4()
        case = _make_case(db, batch_id=batch_id)
        run_batch(db, now=NOW, case_ids=[case.id])  # fraud -> escalated_human

        matching = list_cases(db, batch_id=batch_id, status="escalated_human", case_type="payment_failure")
        non_matching = list_cases(db, batch_id=batch_id, status="recovered")

        assert len(matching) == 1
        assert matching[0].id == case.id
        assert non_matching == []
    finally:
        db.close()
