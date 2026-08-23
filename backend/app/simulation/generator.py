"""Synthetic environment generator (PRD §12).

Produces Customer + Case rows as plain dicts, ready for bulk insert. Case
type mix is weighted toward payment_failure (which itself is weighted
toward insufficient_funds/card_expired), with mandate_failure and
receivable as the other two leak types. `root_cause` is intentionally left
null here — it's filled by the detection layer (Phase 2), not the
generator, so detection is a genuine classification step and not a lookup.

A small fraction of payment/mandate cases get an ambiguous free-text
failure message (no deterministic decline code) specifically to force the
Phase 2 LLM-fallback classification path.
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

from app.constants import CARD_ON_FILE_STATUSES, PREFERRED_CHANNELS, RESPONSIVENESS_PROFILES

RAW_FAILURE_MESSAGES: dict[str, list[str]] = {
    "insufficient_funds": [
        "NSF: Insufficient funds in account",
        "Decline code 51: insufficient funds",
    ],
    "card_expired": [
        "Card expired",
        "Decline code 54: expired card",
    ],
    "issuer_declined": [
        "Issuer declined the transaction",
        "Decline code 05: do not honor",
    ],
    "bank_timeout": [
        "Bank timeout - no response from issuer",
        "Decline code 91: issuer unavailable",
    ],
    "fraud_suspected": [
        "Suspected fraud - transaction blocked",
        "Decline code 59: suspected fraud",
    ],
    "mandate_revoked": [
        "Mandate revoked by customer",
        "NACH return code MD01: mandate cancelled",
    ],
}

AMBIGUOUS_MESSAGES = [
    "Transaction could not be completed. Please contact your bank.",
    "Payment failed. Reason not specified by processor.",
    "Debit unsuccessful, generic decline.",
]

PAYMENT_ROOT_CAUSE_WEIGHTS = [
    ("insufficient_funds", 0.40),
    ("card_expired", 0.25),
    ("issuer_declined", 0.15),
    ("bank_timeout", 0.10),
    ("fraud_suspected", 0.05),
    ("__ambiguous__", 0.05),
]

MANDATE_ROOT_CAUSE_WEIGHTS = [
    ("mandate_revoked", 0.55),
    ("insufficient_funds", 0.25),
    ("issuer_declined", 0.15),
    ("__ambiguous__", 0.05),
]

CASE_TYPE_WEIGHTS = [
    ("payment_failure", 0.55),
    ("mandate_failure", 0.15),
    ("receivable", 0.30),
]


def _weighted_choice(rng: random.Random, weights: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in weights)
    r = rng.random() * total
    upto = 0.0
    for value, w in weights:
        upto += w
        if r <= upto:
            return value
    return weights[-1][0]


def _gen_customer(rng: random.Random) -> dict:
    return {
        "id": uuid.uuid4(),
        "dnd_registered": rng.random() < 0.20,
        "responsiveness_profile": _weighted_choice(rng, [(p, 1) for p in RESPONSIVENESS_PROFILES]),
        "preferred_channel": _weighted_choice(rng, [(c, 1) for c in PREFERRED_CHANNELS]),
        "card_on_file_status": _weighted_choice(rng, [(s, 1) for s in CARD_ON_FILE_STATUSES]),
    }


def _gen_payment_or_mandate_case(rng: random.Random, case_type: str, customer_id: uuid.UUID, now: datetime) -> dict:
    weights = PAYMENT_ROOT_CAUSE_WEIGHTS if case_type == "payment_failure" else MANDATE_ROOT_CAUSE_WEIGHTS
    true_cause = _weighted_choice(rng, weights)
    raw = rng.choice(AMBIGUOUS_MESSAGES) if true_cause == "__ambiguous__" else rng.choice(RAW_FAILURE_MESSAGES[true_cause])
    amount = round(rng.uniform(200, 25000), 2)
    return {
        "id": uuid.uuid4(),
        "type": case_type,
        "customer_id": customer_id,
        "amount": amount,
        "currency": "INR",
        "created_at": now - timedelta(days=rng.randint(0, 5)),
        "due_at": None,
        "status": "open",
        "raw_failure_reason": raw,
        "root_cause": None,
        "outcome": "pending",
        "recovered_amount": 0,
    }


def _gen_receivable_case(rng: random.Random, customer_id: uuid.UUID, now: datetime) -> dict:
    amount = round(rng.uniform(5000, 500000), 2)
    bucket = rng.choice(["early", "mid", "late"])
    days_overdue = {
        "early": rng.randint(0, 15),
        "mid": rng.randint(16, 45),
        "late": rng.randint(46, 90),
    }[bucket]
    due_at = now - timedelta(days=days_overdue)
    return {
        "id": uuid.uuid4(),
        "type": "receivable",
        "customer_id": customer_id,
        "amount": amount,
        "currency": "INR",
        "created_at": due_at,
        "due_at": due_at,
        "status": "open",
        "raw_failure_reason": None,
        "root_cause": None,
        "outcome": "pending",
        "recovered_amount": 0,
    }


def generate_batch(n_cases: int = 200, seed: int | None = None) -> tuple[list[dict], list[dict]]:
    """Returns (customers, cases) as lists of plain dicts, one customer per case."""
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    customers: list[dict] = []
    cases: list[dict] = []
    for _ in range(n_cases):
        customer = _gen_customer(rng)
        customers.append(customer)
        case_type = _weighted_choice(rng, CASE_TYPE_WEIGHTS)
        if case_type == "receivable":
            case = _gen_receivable_case(rng, customer["id"], now)
        else:
            case = _gen_payment_or_mandate_case(rng, case_type, customer["id"], now)
        cases.append(case)
    return customers, cases
