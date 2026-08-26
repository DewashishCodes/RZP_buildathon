"""Enumerations shared across the app. Kept as plain string constants (not
DB-level enums) so new values don't require a migration — see app/models.py.
"""

CASE_TYPES = ["payment_failure", "mandate_failure", "receivable"]

CASE_STATUSES = ["open", "recovering", "recovered", "written_off", "escalated_human"]

CASE_OUTCOMES = ["recovered", "unrecovered", "pending"]

RESPONSIVENESS_PROFILES = ["cooperative", "evasive", "unresponsive", "hostile"]

PREFERRED_CHANNELS = ["sms", "email", "voice", "whatsapp"]

CARD_ON_FILE_STATUSES = ["valid", "expired", "insufficient_funds_pattern"]

ATTEMPT_CHANNELS = ["silent_retry", "sms_nudge", "email_link", "voice_call", "human_escalation", "webhook"]

ATTEMPT_OUTCOMES = ["success", "failure", "no_response", "opt_out", "promise_to_pay"]

# PRD §7 root cause taxonomy
PAYMENT_ROOT_CAUSES = [
    "insufficient_funds",
    "card_expired",
    "issuer_declined",
    "bank_timeout",
    "fraud_suspected",
    "mandate_revoked",
]

RECEIVABLE_ROOT_CAUSES = [
    "overdue_early",
    "overdue_mid",
    "overdue_late",
    "disputed",
]

ROOT_CAUSES = PAYMENT_ROOT_CAUSES + RECEIVABLE_ROOT_CAUSES

# PRD §8 bounded action space
ACTIONS = [
    "no_action",
    "retry_now",
    "retry_scheduled",
    "send_update_link",
    "send_reminder",
    "request_promise_to_pay",
    "voice_call",
    "escalate_human",
    "stop_case",
]

AUDIT_EVENT_TYPES = [
    "detected",
    "diagnosed",
    "action_proposed",
    "compliance_check",
    "action_executed",
    "outcome_recorded",
    "stopped",
    "escalated",
    "webhook_received",
]

AUDIT_ACTORS = ["system", "llm", "human"]

TICKET_STATUSES = ["open", "in_progress", "resolved"]

TICKET_PRIORITIES = ["low", "normal", "high", "urgent"]
