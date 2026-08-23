"""Mock channel connectors (PRD §5, §9.1 step 4). Each contact action rolls
against the hidden recoverability model (app/simulation/recoverability.py)
and returns a normalized outcome the batch runner turns into an Attempt +
AuditEvents. Only this layer is allowed to import the recoverability
model - detection and policy code never see it.

`voice_call` gets a plain recoverability-model roll here, same as any
other contact action, as a stand-in so a full batch can still reach a
terminal state end to end. Phase 5 replaces this with the real two-role
Hinglish conversation + transcript extraction; the recoverability roll
itself doesn't change, only how the outcome is produced.
"""
import random
from datetime import date, datetime, timedelta

from app.simulation.recoverability import roll_outcome

# Customers who won't engage sometimes opt out outright rather than just
# not responding. Not part of the core hidden recoverability model (that's
# about whether an engaged customer recovers) - this is about whether they
# engage with the channel at all, layered on top here.
OPT_OUT_CHANCE_BY_PROFILE: dict[str, float] = {"hostile": 0.15}

PROMISE_TO_PAY_HORIZON_DAYS = 5


def _roll_opt_out(customer, rng: random.Random) -> bool:
    chance = OPT_OUT_CHANCE_BY_PROFILE.get(customer.responsiveness_profile, 0.0)
    return rng.random() < chance


def execute_contact_action(case, customer, action: str, now: datetime, rng: random.Random | None = None) -> dict:
    """Rolls an outcome for a contact action (retry_now, retry_scheduled,
    send_update_link, send_reminder, request_promise_to_pay, voice_call).
    Returns {attempt_outcome, recovered, recovered_amount, promise_to_pay_date}.
    """
    rng = rng or random.Random()

    if action not in ("retry_now", "retry_scheduled") and _roll_opt_out(customer, rng):
        return {"attempt_outcome": "opt_out", "recovered": False, "recovered_amount": 0.0, "promise_to_pay_date": None}

    roll = roll_outcome(case.root_cause, action, customer.responsiveness_profile, rng=rng)

    if "promise_given" in roll:
        if not roll["promise_given"]:
            return {"attempt_outcome": "no_response", "recovered": False, "recovered_amount": 0.0, "promise_to_pay_date": None}
        honored = bool(roll.get("promise_honored", False))
        promise_date: date = (now + timedelta(days=PROMISE_TO_PAY_HORIZON_DAYS)).date()
        return {
            "attempt_outcome": "promise_to_pay",
            "recovered": honored,
            "recovered_amount": float(case.amount) if honored else 0.0,
            "promise_to_pay_date": promise_date,
        }

    if "link_clicked" in roll:
        if not roll["link_clicked"]:
            return {"attempt_outcome": "no_response", "recovered": False, "recovered_amount": 0.0, "promise_to_pay_date": None}
        success = bool(roll["success"])
        return {
            "attempt_outcome": "success" if success else "failure",
            "recovered": success,
            "recovered_amount": float(case.amount) if success else 0.0,
            "promise_to_pay_date": None,
        }

    success = bool(roll["success"])
    return {
        "attempt_outcome": "success" if success else "failure",
        "recovered": success,
        "recovered_amount": float(case.amount) if success else 0.0,
        "promise_to_pay_date": None,
    }
