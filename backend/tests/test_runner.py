import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.execution.runner import TERMINAL_STATUSES, process_due_cases, run_batch
from app.models import Case, Customer, Ticket
from tests.fakes import FakeGeminiClient


def _make_case(db, raw_failure_reason, responsiveness_profile="hostile", case_type="payment_failure"):
    customer = Customer(
        id=uuid.uuid4(),
        dnd_registered=False,
        responsiveness_profile=responsiveness_profile,
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
        created_at=datetime.now(timezone.utc),
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


def test_run_batch_terminates_every_case():
    db = SessionLocal()
    try:
        cases = [
            _make_case(db, "Card expired"),  # near-0% retry_now success -> guardrail caps retries -> escalate
            _make_case(db, "Decline code 59: suspected fraud"),  # auto-escalate immediately
            _make_case(db, "Mandate revoked by customer", case_type="mandate_failure"),
        ]
        # Always propose retry_now regardless of case - guardrails must still
        # force every case to a terminal state within MAX_ROUNDS_PER_CASE,
        # proving PRD §9.2's "no case stays in limbo" requirement holds
        # even when the LLM keeps proposing the same thing.
        always_retry_client = FakeGeminiClient(
            response_text='{"action": "retry_now", "params": {}, "rationale": "keep retrying"}'
        )

        run_batch(db, llm_client=always_retry_client)

        for case in cases:
            db.refresh(case)
            assert case.status in TERMINAL_STATUSES
    finally:
        db.close()


def test_run_batch_fraud_case_escalates_without_any_retries():
    db = SessionLocal()
    try:
        case = _make_case(db, "Decline code 59: suspected fraud")
        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "n/a"}')

        run_batch(db, llm_client=client)
        db.refresh(case)

        assert case.status == "escalated_human"
        assert len(case.attempts) == 0  # no contact attempts - fraud skips straight to escalation

        ticket = db.execute(select(Ticket).where(Ticket.case_id == case.id)).scalar_one_or_none()
        assert ticket is not None
        assert ticket.priority == "urgent"
    finally:
        db.close()


def test_run_batch_summary_reflects_recovered_amounts():
    db = SessionLocal()
    try:
        case = _make_case(db, "Bank timeout - no response from issuer", responsiveness_profile="cooperative")
        # bank_timeout + retry_now has a high base success rate, so a
        # cooperative customer should recover quickly in most runs.
        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "transient, retry"}')

        summary = run_batch(db, llm_client=client)
        db.refresh(case)

        assert summary["total_cases"] >= 1
        assert summary["total_at_risk"] >= float(case.amount)
        if case.status == "recovered":
            assert case.recovered_amount == float(case.amount)
            assert summary["total_recovered"] >= float(case.amount)
    finally:
        db.close()


def test_run_batch_non_instant_stops_after_one_round():
    db = SessionLocal()
    try:
        case = _make_case(db, "Card expired")  # near-0% retry_now success, won't recover round 1
        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "n/a"}')

        run_batch(db, llm_client=client, instant=False)
        db.refresh(case)

        assert case.status not in TERMINAL_STATUSES
        assert case.status == "recovering"
        assert case.next_action_at is not None
        assert len(case.attempts) == 1  # exactly one round happened, not several
    finally:
        db.close()


def test_run_batch_non_instant_fraud_case_still_terminates_immediately():
    db = SessionLocal()
    try:
        case = _make_case(db, "Decline code 59: suspected fraud")
        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "n/a"}')

        run_batch(db, llm_client=client, instant=False)
        db.refresh(case)

        # a stopping rule fires on round one regardless of instant/non-instant
        assert case.status == "escalated_human"
        assert case.next_action_at is None
    finally:
        db.close()


def test_process_due_cases_advances_scheduled_cases_to_terminal():
    db = SessionLocal()
    try:
        case = _make_case(db, "Card expired")
        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "n/a"}')

        run_batch(db, llm_client=client, instant=False)
        db.refresh(case)
        assert case.next_action_at is not None  # scheduled after round 1

        # keep advancing until it terminates (card_expired + retry_now
        # almost never succeeds, so guardrails will eventually escalate it)
        for _ in range(5):
            db.refresh(case)
            if case.status in TERMINAL_STATUSES:
                break
            process_due_cases(db, llm_client=client)

        db.refresh(case)
        assert case.status in TERMINAL_STATUSES
        assert case.next_action_at is None
    finally:
        db.close()


def test_process_due_cases_reports_counts():
    db = SessionLocal()
    try:
        case = _make_case(db, "Decline code 59: suspected fraud")
        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "n/a"}')

        run_batch(db, llm_client=client, instant=False)
        db.refresh(case)
        assert case.status == "escalated_human"  # fraud terminates round 1, nothing left scheduled for it

        result = process_due_cases(db, llm_client=client)
        assert result["processed"] == 0  # nothing scheduled since the only case already terminated
    finally:
        db.close()
