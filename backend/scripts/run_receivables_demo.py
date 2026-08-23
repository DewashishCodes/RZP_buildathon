"""CLI: run a small, hand-built receivables-only batch end to end and
print each case's outcome (Phase 6 manual walkthrough). Scoped to just
these cases via run_batch's case_ids filter, so it doesn't sweep the
whole accumulated dev DB or burn LLM quota on unrelated cases.

Scenarios: a disputed invoice (should route straight to human, no
auto-chase), an overdue_late invoice (should escalate toward voice_call),
and an overdue_mid invoice (a realistic promise-to-pay candidate).

Usage:
    python scripts/run_receivables_demo.py
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.execution.runner import run_batch
from app.models import AuditEvent, Case, Customer

NOW = datetime.now(timezone.utc)


class _ForcedFirstProposalClient:
    """Forces the *first* LLM call's response (the policy proposal) so the
    voice_call / promise_to_pay scenarios are guaranteed to show up in the
    demo - proving the plumbing (allowed actions, guardrails, connectors,
    audit trail) supports these actions for receivables, not testing
    whether the LLM spontaneously picks them for a first-contact
    cooperative customer (it usually reasonably starts with a gentle
    reminder instead, as seen in an earlier run of this script).

    Every call after the first delegates to the real Gemini client, so a
    forced voice_call proposal still gets a genuine Hinglish conversation
    + extraction afterward, not a garbled fake transcript.
    """

    def __init__(self, action: str, params: dict | None = None, rationale: str = "forced for demo"):
        import json

        from app.detection.gemini_client import get_client

        self._forced_text = json.dumps({"action": action, "params": params or {}, "rationale": rationale})
        self._used = False
        self._real_client = get_client()

        class _Models:
            def __init__(self, outer):
                self._outer = outer

            def generate_content(self, model, contents):
                if not self._outer._used:
                    self._outer._used = True

                    class _Resp:
                        pass

                    resp = _Resp()
                    resp.text = self._outer._forced_text
                    return resp
                return self._outer._real_client.models.generate_content(model=model, contents=contents)

        self.models = _Models(self)


def _make_case(db, days_overdue, disputed=False, amount=75000, responsiveness_profile="cooperative", dnd_registered=False):
    customer = Customer(
        id=uuid.uuid4(),
        dnd_registered=dnd_registered,
        responsiveness_profile=responsiveness_profile,
        preferred_channel="email",
        card_on_file_status="valid",
    )
    db.add(customer)
    case = Case(
        id=uuid.uuid4(),
        type="receivable",
        customer_id=customer.id,
        amount=amount,
        currency="INR",
        created_at=NOW - timedelta(hours=1),
        due_at=NOW - timedelta(days=days_overdue),
        status="open",
        raw_failure_reason=None,
        root_cause=None,
        outcome="pending",
        recovered_amount=0,
        disputed=disputed,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def main() -> None:
    db = SessionLocal()
    try:
        disputed_case = _make_case(db, days_overdue=20, disputed=True)
        late_case = _make_case(db, days_overdue=60)
        mid_case = _make_case(db, days_overdue=25, responsiveness_profile="cooperative")

        # Disputed: no LLM needed at all, the stopping rule fires outright.
        run_batch(db, now=NOW, case_ids=[disputed_case.id])

        # Forced to prove voice_call/request_promise_to_pay are wired up
        # end to end for receivables - see _ForcedFirstProposalClient above.
        voice_client = _ForcedFirstProposalClient("voice_call", rationale="60 days overdue, escalate to a call")
        run_batch(db, now=NOW, case_ids=[late_case.id], llm_client=voice_client)

        promise_client = _ForcedFirstProposalClient("request_promise_to_pay", rationale="ask for a committed payment date")
        run_batch(db, now=NOW, case_ids=[mid_case.id], llm_client=promise_client)

        for label, case_id in [("DISPUTED (20d overdue)", disputed_case.id), ("OVERDUE_LATE (60d overdue)", late_case.id), ("OVERDUE_MID (25d overdue)", mid_case.id)]:
            case = db.execute(select(Case).where(Case.id == case_id)).scalar_one()
            print(f"\n=== {label} ===")
            print(f"  root_cause={case.root_cause} final_status={case.status} outcome={case.outcome} recovered_amount={case.recovered_amount}")
            events = db.execute(select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.timestamp)).scalars().all()
            for e in events:
                print(f"    [{e.event_type:18s} actor={e.actor:8s}] {e.payload}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
