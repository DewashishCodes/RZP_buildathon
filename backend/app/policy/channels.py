"""Maps a bounded-action-space action to the Attempt.channel it's delivered
through, factoring in the customer's preferred_channel where relevant.
"""
ACTION_TO_CHANNEL: dict[str, str | None] = {
    "no_action": None,
    "retry_now": "silent_retry",
    "retry_scheduled": "silent_retry",
    "send_update_link": "email_link",  # overridden below for sms-preferring customers
    "send_reminder": "email_link",
    "request_promise_to_pay": "email_link",
    "voice_call": "voice_call",
    "escalate_human": "human_escalation",
    "stop_case": None,
}

SMS_LIKE_PREFERENCES = {"sms", "whatsapp"}


def determine_channel(action: str, preferred_channel: str) -> str | None:
    base_channel = ACTION_TO_CHANNEL.get(action)
    if base_channel == "email_link" and preferred_channel in SMS_LIKE_PREFERENCES:
        return "sms_nudge"
    return base_channel
