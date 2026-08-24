"""Deliberately hand-crafted cases guaranteed to appear in every seeded
batch (Phase 9, PRD §16: "don't rely on random generation alone"). The
random generator (generator.py) makes no promises about which scenarios
show up in a given batch, and the demo's recommended small batch size
(~10-15 cases, see CLAUDE.md's rate-limit notes) makes that worse - a
guardrail-fired case or a DND compliance substitution might just not
happen to appear.

Four of these are fully deterministic guarantees: they trip a
`check_stopping_rules` branch (app/policy/guardrails.py) on the very
first policy round, which is pure code with no LLM involvement, so the
outcome cannot vary run to run.

The other two (DND-vs-voice_call, promise-to-pay) depend on what the
real Gemini policy call actually proposes for a given case - there is no
way to force that without substituting a fixed LLM response (as
scripts/run_policy_demo.py does for its own scripted walkthrough), which
would defeat the point of a live seeded batch. Instead these two are
built with context deliberately biased toward the scenario: a DND
customer with a severely overdue, high-value, already-nudged-by-SMS
receivable is the shape of case a real recovery policy should escalate
to a call, and a cooperative customer on a mid-overdue receivable is the
shape most likely to produce a promise-to-pay. Likely, not guaranteed.
"""
import uuid
from datetime import datetime, timedelta, timezone

NOW_PLACEHOLDER = None  # replaced per-call in build_guaranteed_cases


def _customer(**kwargs) -> dict:
    return {
        "id": uuid.uuid4(),
        "dnd_registered": kwargs.get("dnd_registered", False),
        "responsiveness_profile": kwargs.get("responsiveness_profile", "cooperative"),
        "preferred_channel": kwargs.get("preferred_channel", "sms"),
        "card_on_file_status": kwargs.get("card_on_file_status", "valid"),
    }


def _payment_case(customer_id, now, **kwargs) -> dict:
    return {
        "id": uuid.uuid4(),
        "type": kwargs.get("type", "payment_failure"),
        "customer_id": customer_id,
        "amount": kwargs.get("amount", 5000),
        "currency": "INR",
        "created_at": kwargs.get("created_at", now - timedelta(days=1)),
        "due_at": None,
        "status": "open",
        "raw_failure_reason": kwargs.get("raw_failure_reason", "Decline code 51: insufficient funds"),
        "root_cause": None,
        "outcome": "pending",
        "recovered_amount": 0,
        "disputed": False,
    }


def _receivable_case(customer_id, now, **kwargs) -> dict:
    return {
        "id": uuid.uuid4(),
        "type": "receivable",
        "customer_id": customer_id,
        "amount": kwargs.get("amount", 50000),
        "currency": "INR",
        "created_at": kwargs.get("created_at", now - timedelta(hours=6)),
        "due_at": kwargs.get("due_at"),
        "status": "open",
        "raw_failure_reason": None,
        "root_cause": None,
        "outcome": "pending",
        "recovered_amount": 0,
        "disputed": kwargs.get("disputed", False),
    }


def _attempt(case_id, now, **kwargs) -> dict:
    return {
        "id": uuid.uuid4(),
        "case_id": case_id,
        "timestamp": kwargs.get("timestamp", now - timedelta(days=1)),
        "channel": kwargs.get("channel", "sms_nudge"),
        "action": kwargs.get("action", "send_reminder"),
        "compliance_check": {"passed": True, "rule": None, "reason": None},
        "outcome": kwargs.get("outcome", "no_response"),
        "promise_to_pay_date": None,
        "transcript": None,
    }


def build_guaranteed_cases(now: datetime | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (customers, cases, attempts) as plain dicts, ready for
    bulk_insert_mappings alongside the random batch - same shape as
    generator.generate_batch, plus attempts for the scenarios that need
    pre-existing contact history to trip their guardrail.
    """
    now = now or datetime.now(timezone.utc)
    customers: list[dict] = []
    cases: list[dict] = []
    attempts: list[dict] = []

    # 1. Guaranteed stopping rule: fraud_or_dispute_auto_escalate (payment).
    fraud_customer = _customer()
    fraud_case = _payment_case(
        fraud_customer["id"], now,
        amount=18000,
        raw_failure_reason="Decline code 59: suspected fraud",
    )
    customers.append(fraud_customer)
    cases.append(fraud_case)

    # 2. Guaranteed stopping rule: fraud_or_dispute_auto_escalate (receivable).
    disputed_customer = _customer(responsiveness_profile="evasive")
    disputed_case = _receivable_case(
        disputed_customer["id"], now,
        amount=120000,
        due_at=now - timedelta(days=20),
        disputed=True,
    )
    customers.append(disputed_customer)
    cases.append(disputed_case)

    # 3. Guaranteed stopping rule: max_total_contacts (4 prior attempts).
    exhausted_customer = _customer(preferred_channel="email")
    exhausted_case = _payment_case(
        exhausted_customer["id"], now,
        amount=7500,
        raw_failure_reason="Decline code 91: issuer unavailable",
    )
    customers.append(exhausted_customer)
    cases.append(exhausted_case)
    attempts.extend([
        _attempt(exhausted_case["id"], now, timestamp=now - timedelta(days=4), channel="sms_nudge", action="send_reminder", outcome="no_response"),
        _attempt(exhausted_case["id"], now, timestamp=now - timedelta(days=3), channel="email_link", action="send_update_link", outcome="no_response"),
        _attempt(exhausted_case["id"], now, timestamp=now - timedelta(days=2), channel="silent_retry", action="retry_now", outcome="failure"),
        _attempt(exhausted_case["id"], now, timestamp=now - timedelta(days=1), channel="voice_call", action="voice_call", outcome="no_response"),
    ])

    # 4. Guaranteed stopping rule: case_age_exceeded (case open >14 days).
    stale_customer = _customer(responsiveness_profile="unresponsive")
    stale_case = _payment_case(
        stale_customer["id"], now,
        amount=3200,
        raw_failure_reason="Decline code 05: do not honor",
        created_at=now - timedelta(days=16),
    )
    customers.append(stale_customer)
    cases.append(stale_case)

    # 5. Biased (not guaranteed): DND customer, severely overdue high-value
    # receivable, already SMS-nudged - the shape of case a policy should
    # escalate to voice_call, which the DND compliance rule then must
    # substitute back to send_reminder.
    dnd_customer = _customer(dnd_registered=True, preferred_channel="voice", responsiveness_profile="unresponsive")
    dnd_case = _receivable_case(
        dnd_customer["id"], now,
        amount=280000,
        due_at=now - timedelta(days=60),
    )
    customers.append(dnd_customer)
    cases.append(dnd_case)
    attempts.append(
        _attempt(dnd_case["id"], now, timestamp=now - timedelta(days=2), channel="sms_nudge", action="send_reminder", outcome="no_response")
    )

    # 6. Biased (not guaranteed): cooperative customer, mid-overdue
    # receivable - the shape most likely to produce a promise-to-pay,
    # honored or broken.
    ptp_customer = _customer(responsiveness_profile="cooperative", preferred_channel="sms")
    ptp_case = _receivable_case(
        ptp_customer["id"], now,
        amount=65000,
        due_at=now - timedelta(days=25),
    )
    customers.append(ptp_customer)
    cases.append(ptp_case)

    return customers, cases, attempts
