import uuid
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.execution.providers import LoggingChannelProvider, ProviderReceipt
from app.execution.runner import run_batch
from app.models import AuditEvent, Case, Customer
from tests.fakes import FakeGeminiClient


def _make_case(db) -> Case:
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
        amount=1000,
        currency="INR",
        created_at=datetime.now(timezone.utc),
        status="open",
        raw_failure_reason="Insufficient funds",
        root_cause=None,
        outcome="pending",
        recovered_amount=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_logging_provider_returns_a_receipt():
    provider = LoggingChannelProvider()
    receipt = provider.send(channel="sms_nudge", action="send_reminder", case_id=uuid.uuid4(), customer_id=uuid.uuid4())
    assert receipt.provider == "logging_mock"
    assert receipt.status == "sent"
    assert receipt.receipt_id


def test_run_batch_records_provider_receipt_on_action_executed():
    db = SessionLocal()
    try:
        case = _make_case(db)
        client = FakeGeminiClient(response_text='{"action": "send_reminder", "params": {}, "rationale": "n/a"}')

        run_batch(db, llm_client=client)

        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.case_id == case.id, AuditEvent.event_type == "action_executed")
            .all()
        )
        assert events, "expected at least one action_executed event"
        receipt = events[0].payload["provider_receipt"]
        assert receipt["provider"] == "logging_mock"
        assert receipt["status"] == "sent"
    finally:
        db.close()


def test_run_batch_accepts_a_custom_provider():
    """Proves the seam is real: a different ChannelProvider implementation
    can be swapped in without touching the runner or recoverability model."""

    class RecordingProvider:
        def __init__(self):
            self.sent = []

        def send(self, *, channel, action, case_id, customer_id):
            self.sent.append((channel, action))
            return ProviderReceipt(provider="test_double", receipt_id="rid-1", status="sent")

    db = SessionLocal()
    try:
        _make_case(db)
        client = FakeGeminiClient(response_text='{"action": "send_reminder", "params": {}, "rationale": "n/a"}')
        provider = RecordingProvider()

        run_batch(db, llm_client=client, provider=provider)

        assert provider.sent, "custom provider was never invoked"
    finally:
        db.close()
