"""Mock Razorpay webhook ingestion - the "how does this touch real
Razorpay" answer for the submission. The batch runner's channel
connectors simulate a hidden recoverability model rolling dice; this
route is the other, real-world half of the picture: an event arriving
*from* a payment gateway after the fact, updating a case the same way a
production integration would.

Signature verification matches Razorpay's actual webhook scheme:
X-Razorpay-Signature is the HMAC-SHA256 hex digest of the raw request
body, keyed by a shared secret configured in the Razorpay dashboard.
RAZORPAY_WEBHOOK_SECRET is empty by default so the demo doesn't require
provisioning a secret just to try the endpoint - set it to turn on real
verification (400 on a bad/missing signature).
"""
import hashlib
import hmac
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import Attempt, AuditEvent, Case

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

# Only these two are handled - Razorpay sends many other event types
# (refund.*, order.*, ...) that don't map to anything in this app's
# recovery-case model.
_TERMINAL_EVENTS = {"payment.captured", "payment.failed"}


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    if not settings.razorpay_webhook_secret:
        return
    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header.")
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    _verify_signature(raw_body, x_razorpay_signature)

    body = await request.json()
    event = body.get("event")
    if event not in _TERMINAL_EVENTS:
        # Not an error - Razorpay expects a 200 for any event it sends,
        # including ones this integration doesn't act on, or it will keep
        # retrying delivery.
        return {"status": "ignored", "reason": f"unhandled event type: {event}"}

    try:
        entity = body["payload"]["payment"]["entity"]
        case_id = uuid.UUID(entity["notes"]["case_id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Malformed payload: missing payload.payment.entity.notes.case_id ({exc})")

    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No case found for case_id {case_id}")

    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            case_id=case.id,
            event_type="webhook_received",
            actor="system",
            payload={"event": event, "razorpay_payment_id": entity.get("id")},
        )
    )

    if case.status in {"recovered", "written_off", "escalated_human"}:
        logger.info("razorpay_webhook_ignored_terminal_case", extra={"case_id": str(case.id), "event": event})
        db.commit()
        return {"status": "ok", "case_id": str(case.id), "applied": False, "reason": "case already terminal"}

    if event == "payment.captured":
        case.status = "recovered"
        case.outcome = "recovered"
        case.recovered_amount = case.amount
        case.next_action_at = None
        db.add(case)
        attempt = Attempt(
            id=uuid.uuid4(),
            case_id=case.id,
            channel="webhook",
            action="retry_now",
            compliance_check={"passed": True, "source": "razorpay_webhook"},
            outcome="success",
            promise_to_pay_date=None,
        )
        db.add(attempt)
        db.add(
            AuditEvent(
                id=uuid.uuid4(),
                case_id=case.id,
                attempt_id=attempt.id,
                event_type="outcome_recorded",
                actor="system",
                payload={"outcome": "success", "recovered": True, "recovered_amount": float(case.amount), "source": "razorpay_webhook"},
            )
        )
        applied = True
    else:  # payment.failed
        attempt = Attempt(
            id=uuid.uuid4(),
            case_id=case.id,
            channel="webhook",
            action="retry_now",
            compliance_check={"passed": True, "source": "razorpay_webhook"},
            outcome="failure",
            promise_to_pay_date=None,
        )
        db.add(attempt)
        db.add(
            AuditEvent(
                id=uuid.uuid4(),
                case_id=case.id,
                attempt_id=attempt.id,
                event_type="outcome_recorded",
                actor="system",
                payload={"outcome": "failure", "recovered": False, "recovered_amount": 0.0, "source": "razorpay_webhook"},
            )
        )
        # A failed retry doesn't resolve the case by itself - the next
        # scheduled/manual round still decides whether to retry, escalate,
        # or stop, same as any other failed attempt.
        applied = True

    db.commit()
    logger.info("razorpay_webhook_applied", extra={"case_id": str(case.id), "event": event})
    return {"status": "ok", "case_id": str(case.id), "applied": applied}
