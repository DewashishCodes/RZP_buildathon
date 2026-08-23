"""Regression test: multiple AuditEvents created in the same flush must
get distinct, chronologically ordered timestamps. datetime.utcnow() as a
Python-side default was observed producing byte-identical timestamps for
events written back-to-back (e.g. action_proposed + compliance_check),
which breaks PRD §11's "drillable to a full timeline" requirement.
Server-side clock_timestamp() (app/models.py) fixes this.
"""
import uuid
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models import AuditEvent, Case, Customer


def test_audit_events_in_same_flush_get_strictly_increasing_timestamps():
    db = SessionLocal()
    try:
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
            root_cause="insufficient_funds",
            outcome="pending",
            recovered_amount=0,
        )
        db.add(case)
        db.commit()

        events = [
            AuditEvent(id=uuid.uuid4(), case_id=case.id, event_type="detected", actor="system", payload={}),
            AuditEvent(id=uuid.uuid4(), case_id=case.id, event_type="diagnosed", actor="system", payload={}),
            AuditEvent(id=uuid.uuid4(), case_id=case.id, event_type="action_proposed", actor="llm", payload={}),
            AuditEvent(id=uuid.uuid4(), case_id=case.id, event_type="compliance_check", actor="system", payload={}),
        ]
        db.add_all(events)
        db.commit()
        for e in events:
            db.refresh(e)

        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)
        assert len(set(timestamps)) == len(timestamps)  # strictly distinct, not just non-decreasing
    finally:
        db.close()
