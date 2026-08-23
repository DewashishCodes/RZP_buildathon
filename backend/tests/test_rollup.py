import uuid
from datetime import datetime, timezone

from app.audit.rollup import batch_summary
from app.db.session import SessionLocal
from app.execution.runner import run_batch
from app.models import Case, Customer
from tests.fakes import FakeGeminiClient

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _make_case(db, batch_id, raw_failure_reason, amount, dnd_registered=False):
    customer = Customer(
        id=uuid.uuid4(),
        dnd_registered=dnd_registered,
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


def test_batch_summary_returns_none_for_unknown_batch():
    db = SessionLocal()
    try:
        result = batch_summary(db, uuid.uuid4())
        assert result is None
    finally:
        db.close()


def test_batch_summary_aggregates_only_this_batchs_cases():
    db = SessionLocal()
    try:
        batch_id = uuid.uuid4()
        other_batch_id = uuid.uuid4()

        fraud_case = _make_case(db, batch_id, "Decline code 59: suspected fraud", 5000)
        # DND + a client that always proposes voice_call -> guaranteed compliance substitution every round
        dnd_case = _make_case(db, batch_id, "NSF: Insufficient funds in account", 3000, dnd_registered=True)
        # A case in a different batch must not leak into this batch's summary
        _make_case(db, other_batch_id, "Card expired", 999999)

        voice_client = FakeGeminiClient(response_text='{"action": "voice_call", "params": {}, "rationale": "n/a"}')
        run_batch(db, now=NOW, case_ids=[fraud_case.id], llm_client=voice_client)
        run_batch(db, now=NOW, case_ids=[dnd_case.id], llm_client=voice_client)

        summary = batch_summary(db, batch_id)

        assert summary["batch_id"] == str(batch_id)
        assert summary["total_cases"] == 2
        assert summary["total_at_risk"] == 8000.0
        assert summary["stopping_rule_triggers"] >= 1  # the fraud auto-escalation
        assert summary["compliance_substitutions"] >= 1  # the DND voice_call substitution
        assert "insufficient_funds" in summary["by_root_cause"] or "fraud_suspected" in summary["by_root_cause"]
    finally:
        db.close()


def test_batch_summary_recovery_rate_matches_amounts():
    db = SessionLocal()
    try:
        batch_id = uuid.uuid4()
        case = _make_case(db, batch_id, "Bank timeout - no response from issuer", 10000)

        client = FakeGeminiClient(response_text='{"action": "retry_now", "params": {}, "rationale": "transient"}')
        run_batch(db, now=NOW, case_ids=[case.id], llm_client=client)

        summary = batch_summary(db, batch_id)
        db.refresh(case)

        assert summary["total_at_risk"] == 10000.0
        assert summary["total_recovered"] == float(case.recovered_amount)
        expected_rate = float(case.recovered_amount) / 10000.0
        assert abs(summary["recovery_rate"] - expected_rate) < 1e-9
    finally:
        db.close()
