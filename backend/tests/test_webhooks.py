import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings
from app.db.session import SessionLocal
from app.models import Case, Customer

client = TestClient(app)


def _make_case(db, amount=1000) -> Case:
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
        created_at=datetime.now(timezone.utc),
        status="open",
        raw_failure_reason="Insufficient funds",
        root_cause="insufficient_funds",
        outcome="pending",
        recovered_amount=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _payload(event: str, case_id: uuid.UUID) -> dict:
    return {
        "event": event,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_MockRzp123",
                    "amount": 100000,
                    "notes": {"case_id": str(case_id)},
                }
            }
        },
    }


def test_payment_captured_recovers_the_case():
    db = SessionLocal()
    try:
        case = _make_case(db)
        resp = client.post("/webhooks/razorpay", json=_payload("payment.captured", case.id))

        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok", "case_id": str(case.id), "applied": True}

        db.refresh(case)
        assert case.status == "recovered"
        assert case.outcome == "recovered"
        assert float(case.recovered_amount) == float(case.amount)
        assert any(a.channel == "webhook" and a.outcome == "success" for a in case.attempts)
    finally:
        db.close()


def test_payment_failed_records_attempt_without_resolving_case():
    db = SessionLocal()
    try:
        case = _make_case(db)
        resp = client.post("/webhooks/razorpay", json=_payload("payment.failed", case.id))

        assert resp.status_code == 200
        assert resp.json()["applied"] is True

        db.refresh(case)
        assert case.status == "open"  # a failed retry alone doesn't terminate the case
        assert any(a.channel == "webhook" and a.outcome == "failure" for a in case.attempts)
    finally:
        db.close()


def test_webhook_ignores_terminal_case():
    db = SessionLocal()
    try:
        case = _make_case(db)
        case.status = "recovered"
        db.add(case)
        db.commit()

        resp = client.post("/webhooks/razorpay", json=_payload("payment.captured", case.id))

        assert resp.status_code == 200
        assert resp.json()["applied"] is False
    finally:
        db.close()


def test_webhook_unhandled_event_is_ignored_not_an_error():
    resp = client.post(
        "/webhooks/razorpay",
        json={"event": "refund.processed", "payload": {}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_unknown_case_404():
    resp = client.post("/webhooks/razorpay", json=_payload("payment.captured", uuid.uuid4()))
    assert resp.status_code == 404


def test_webhook_malformed_payload_400():
    resp = client.post("/webhooks/razorpay", json={"event": "payment.captured", "payload": {}})
    assert resp.status_code == 400


def test_webhook_signature_verification(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "test-secret")
    db = SessionLocal()
    try:
        case = _make_case(db)
        body = json.dumps(_payload("payment.captured", case.id)).encode()
        good_sig = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

        missing = client.post("/webhooks/razorpay", content=body, headers={"Content-Type": "application/json"})
        assert missing.status_code == 400

        bad = client.post(
            "/webhooks/razorpay",
            content=body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": "wrong"},
        )
        assert bad.status_code == 400

        good = client.post(
            "/webhooks/razorpay",
            content=body,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": good_sig},
        )
        assert good.status_code == 200
    finally:
        db.close()
