"""CLI: run the policy engine over a handful of hand-picked scenarios,
each designed to trip a specific guardrail, so it's visible that
guardrails actually override the LLM (Phase 3 manual walkthrough).

Creates its own throwaway Customer/Case rows (does not touch a seeded
batch), runs decide_action against the real Gemini API, and prints
proposed action -> guardrail verdict -> final action for each.

Usage:
    python scripts/run_policy_demo.py
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.models import Attempt, Case, Customer
from app.policy.engine import decide_action

NOW = datetime.now(timezone.utc)


class _FixedResponseClient:
    """Forces a specific LLM proposal so the DND guardrail demo is
    deterministic - relying on the real model to happen to propose
    voice_call would make this scenario non-reproducible, and PRD §11
    requires proving substitution actually happens, not hoping it does.
    """

    def __init__(self, action: str, params: dict | None = None, rationale: str = "forced for demo"):
        import json

        self._text = json.dumps({"action": action, "params": params or {}, "rationale": rationale})

        class _Models:
            def __init__(self, outer):
                self._outer = outer

            def generate_content(self, model, contents):
                class _Resp:
                    text = self._outer._text

                return _Resp()

        self.models = _Models(self)


def _make_case(db, **kwargs):
    customer = Customer(
        id=uuid.uuid4(),
        dnd_registered=kwargs.pop("dnd_registered", False),
        responsiveness_profile=kwargs.pop("responsiveness_profile", "cooperative"),
        preferred_channel=kwargs.pop("preferred_channel", "sms"),
        card_on_file_status="valid",
    )
    db.add(customer)
    case = Case(
        id=uuid.uuid4(),
        type=kwargs.pop("type", "payment_failure"),
        customer_id=customer.id,
        amount=kwargs.pop("amount", 2500),
        currency="INR",
        created_at=kwargs.pop("created_at", NOW - timedelta(days=1)),
        due_at=kwargs.pop("due_at", None),
        status="open",
        raw_failure_reason=kwargs.pop("raw_failure_reason", "Decline code 51: insufficient funds"),
        root_cause=kwargs.pop("root_cause", "insufficient_funds"),
        outcome="pending",
        recovered_amount=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    db.refresh(customer)
    return case, customer


def _attempt(case_id, action, channel, outcome, timestamp):
    return Attempt(
        id=uuid.uuid4(),
        case_id=case_id,
        timestamp=timestamp,
        channel=channel,
        action=action,
        compliance_check={"passed": True, "rule": None, "reason": None},
        outcome=outcome,
    )


def scenario_fraud(db):
    case, customer = _make_case(db, root_cause="fraud_suspected", raw_failure_reason="Decline code 59: suspected fraud")
    return "fraud_suspected -> should auto-escalate, LLM never called", case, customer, [], None


def scenario_dnd_voice(db):
    case, customer = _make_case(
        db, type="receivable", root_cause="overdue_late", dnd_registered=True, due_at=NOW - timedelta(days=60),
        raw_failure_reason=None, amount=45000,
    )
    client = _FixedResponseClient("voice_call", rationale="overdue_late warrants an escalation call")
    return "DND customer, LLM proposes voice_call -> guardrail must fall back to send_reminder", case, customer, [], client


def scenario_max_attempts(db):
    case, customer = _make_case(db)
    attempts = [
        _attempt(case.id, "sms_nudge", "sms_nudge", "no_response", NOW - timedelta(days=4)),
        _attempt(case.id, "email_link", "email_link", "no_response", NOW - timedelta(days=3)),
        _attempt(case.id, "retry_now", "silent_retry", "failure", NOW - timedelta(days=2)),
        _attempt(case.id, "voice_call", "voice_call", "no_response", NOW - timedelta(days=1)),
    ]
    db.add_all(attempts)
    db.commit()
    return "4 prior contact attempts (max) -> should auto-escalate, LLM never called", case, customer, attempts, None


def scenario_normal(db):
    case, customer = _make_case(db, root_cause="card_expired", raw_failure_reason="Card expired")
    return "card_expired, no history -> normal LLM proposal + compliance pass expected (real Gemini call)", case, customer, [], None


def main() -> None:
    db = SessionLocal()
    try:
        scenarios = [scenario_fraud, scenario_dnd_voice, scenario_max_attempts, scenario_normal]
        for build in scenarios:
            description, case, customer, attempts, client = build(db)
            print(f"\n=== {description} ===")
            decision = decide_action(db, case, customer, attempts, now=NOW, llm_client=client)
            db.commit()
            print(f"  case_type={case.type} root_cause={case.root_cause}")
            print(f"  final_action={decision['action']} source={decision['source']} rule={decision['rule']} substituted={decision['substituted']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
