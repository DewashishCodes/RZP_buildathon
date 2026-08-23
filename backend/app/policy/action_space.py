"""Per-Case.type allowed action subsets (PRD §8): the LLM proposer and the
guardrail layer both constrain against this, never against the full
ACTIONS list directly.
"""
from app.constants import ACTIONS

PAYMENT_LIKE_ACTIONS = [
    "no_action",
    "retry_now",
    "retry_scheduled",
    "send_update_link",
    "send_reminder",
    "voice_call",
    "escalate_human",
    "stop_case",
]

RECEIVABLE_ACTIONS = [
    "no_action",
    "send_reminder",
    "request_promise_to_pay",
    "voice_call",
    "escalate_human",
    "stop_case",
]

ALLOWED_ACTIONS_BY_TYPE: dict[str, list[str]] = {
    "payment_failure": PAYMENT_LIKE_ACTIONS,
    "mandate_failure": PAYMENT_LIKE_ACTIONS,
    "receivable": RECEIVABLE_ACTIONS,
}

assert all(action in ACTIONS for actions in ALLOWED_ACTIONS_BY_TYPE.values() for action in actions)


def get_allowed_actions(case_type: str) -> list[str]:
    return ALLOWED_ACTIONS_BY_TYPE[case_type]
