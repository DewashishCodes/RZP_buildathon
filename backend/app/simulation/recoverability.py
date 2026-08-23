"""Hidden recoverability model (PRD §12).

This is the module the execution layer (Phase 4) rolls against to produce
outcomes. Detection and policy code must never import this module — the
whole point is that the agent's behavior over a batch is a genuine test of
its reasoning, not a lookup into the answer key.
"""
import random

# Base P(success) per (root_cause, action), before profile/channel modifiers.
BASE_SUCCESS_RATES: dict[tuple[str, str], float] = {
    ("insufficient_funds", "retry_now"): 0.15,
    ("insufficient_funds", "retry_scheduled"): 0.60,
    ("insufficient_funds", "request_promise_to_pay"): 0.30,
    ("card_expired", "send_update_link"): 0.75,  # conditional on link click, see below
    ("card_expired", "retry_now"): 0.02,
    ("issuer_declined", "retry_now"): 0.20,
    ("issuer_declined", "escalate_human"): 0.35,
    ("bank_timeout", "retry_now"): 0.70,
    ("mandate_revoked", "send_update_link"): 0.40,
    # voice_call as an escalation channel for payment/mandate leaks (Phase 5):
    # a human-ish conversation is more persuasive than a nudge but this is a
    # last-resort channel, so still below a well-timed scheduled retry.
    ("insufficient_funds", "voice_call"): 0.45,
    ("card_expired", "voice_call"): 0.50,
    ("issuer_declined", "voice_call"): 0.35,
    ("mandate_revoked", "voice_call"): 0.35,
    ("overdue_early", "send_reminder"): 0.35,
    ("overdue_mid", "send_reminder"): 0.30,
    ("overdue_mid", "request_promise_to_pay"): 0.50,
    ("overdue_late", "voice_call"): 0.40,
    ("overdue_late", "escalate_human"): 0.25,
    ("disputed", "escalate_human"): 0.20,
}

DEFAULT_BASE_RATE = 0.05

PROFILE_MULTIPLIERS: dict[str, float] = {
    "cooperative": 1.15,
    "evasive": 0.85,
    "unresponsive": 0.50,
    "hostile": 0.40,
}

LINK_CLICK_RATE: dict[str, float] = {
    "cooperative": 0.75,
    "evasive": 0.45,
    "unresponsive": 0.20,
    "hostile": 0.15,
}

PROMISE_TO_PAY_GIVEN_HONOR_RATE = 0.70

LINK_ACTIONS = {"send_update_link"}
PROMISE_ACTIONS = {"request_promise_to_pay"}


def get_base_rate(root_cause: str, action: str) -> float:
    return BASE_SUCCESS_RATES.get((root_cause, action), DEFAULT_BASE_RATE)


def roll_outcome(
    root_cause: str,
    action: str,
    responsiveness_profile: str,
    rng: random.Random | None = None,
) -> dict:
    """Rolls a single attempt outcome. Returns a dict with at least
    {"success": bool, "recovered": bool} plus action-specific extras.
    """
    rng = rng or random.Random()

    if root_cause == "fraud_suspected":
        return {"success": False, "recovered": False}

    base = get_base_rate(root_cause, action)
    multiplier = PROFILE_MULTIPLIERS.get(responsiveness_profile, 1.0)
    prob = min(base * multiplier, 0.95)

    if action in LINK_ACTIONS:
        clicked = rng.random() < LINK_CLICK_RATE.get(responsiveness_profile, 0.3)
        if not clicked:
            return {"success": False, "recovered": False, "link_clicked": False}
        success = rng.random() < prob
        return {"success": success, "recovered": success, "link_clicked": True}

    if action in PROMISE_ACTIONS:
        gave_promise = rng.random() < prob
        if not gave_promise:
            return {"success": False, "recovered": False, "promise_given": False}
        honored = rng.random() < PROMISE_TO_PAY_GIVEN_HONOR_RATE
        return {
            "success": honored,
            "recovered": honored,
            "promise_given": True,
            "promise_honored": honored,
        }

    success = rng.random() < prob
    return {"success": success, "recovered": success}
