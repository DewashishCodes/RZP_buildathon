import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.policy.guardrails import check_compliance, check_stopping_rules


def make_case(root_cause=None, created_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        root_cause=root_cause,
        created_at=created_at or datetime.now(timezone.utc),
    )


def make_customer(dnd_registered=False, preferred_channel="sms"):
    return SimpleNamespace(dnd_registered=dnd_registered, preferred_channel=preferred_channel)


def make_attempt(action="retry_now", channel="silent_retry", outcome="failure", timestamp=None):
    return SimpleNamespace(
        action=action,
        channel=channel,
        outcome=outcome,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)  # a Sunday, well within calling hours in IST


# ---- stopping rules ----


def test_fraud_suspected_forces_immediate_escalation():
    case = make_case(root_cause="fraud_suspected")
    result = check_stopping_rules(case, make_customer(), [], now=NOW)
    assert result is not None
    assert result["action"] == "escalate_human"
    assert result["rule"] == "fraud_or_dispute_auto_escalate"


def test_disputed_forces_immediate_escalation():
    case = make_case(root_cause="disputed")
    result = check_stopping_rules(case, make_customer(), [], now=NOW)
    assert result["action"] == "escalate_human"
    assert result["rule"] == "fraud_or_dispute_auto_escalate"


def test_opt_out_forces_stop_case():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(outcome="opt_out")]
    result = check_stopping_rules(case, make_customer(), attempts, now=NOW)
    assert result["action"] == "stop_case"
    assert result["rule"] == "opt_out_honored"


def test_max_total_contacts_forces_escalation():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(action="sms_nudge", channel="sms_nudge") for _ in range(4)]
    result = check_stopping_rules(case, make_customer(), attempts, now=NOW)
    assert result["action"] == "escalate_human"
    assert result["rule"] == "max_total_contacts"


def test_under_max_total_contacts_does_not_fire():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(action="sms_nudge", channel="sms_nudge") for _ in range(3)]
    result = check_stopping_rules(case, make_customer(), attempts, now=NOW)
    assert result is None


def test_max_retry_attempts_forces_escalation():
    case = make_case(root_cause="insufficient_funds")
    attempts = [
        make_attempt(action="retry_now", timestamp=NOW - timedelta(days=3)),
        make_attempt(action="retry_now", timestamp=NOW - timedelta(days=2)),
        make_attempt(action="retry_scheduled", timestamp=NOW - timedelta(days=1)),
    ]
    result = check_stopping_rules(case, make_customer(), attempts, now=NOW)
    assert result["action"] == "escalate_human"
    assert result["rule"] == "max_retry_attempts"


def test_case_age_exceeded_forces_escalation():
    case = make_case(root_cause="insufficient_funds", created_at=NOW - timedelta(days=15))
    result = check_stopping_rules(case, make_customer(), [], now=NOW)
    assert result["action"] == "escalate_human"
    assert result["rule"] == "case_age_exceeded"


def test_fresh_case_with_no_attempts_has_no_stopping_rule():
    case = make_case(root_cause="insufficient_funds", created_at=NOW - timedelta(days=1))
    result = check_stopping_rules(case, make_customer(), [], now=NOW)
    assert result is None


# ---- compliance rules ----


def test_compliant_action_passes_through_unchanged():
    case = make_case(root_cause="insufficient_funds")
    result = check_compliance("send_reminder", {}, case, make_customer(), [], now=NOW)
    assert result["passed"] is True
    assert result["action"] == "send_reminder"
    assert result["substituted"] is False


def test_dnd_blocks_voice_call_and_falls_back_to_send_reminder():
    case = make_case(root_cause="overdue_late")
    customer = make_customer(dnd_registered=True)
    result = check_compliance("voice_call", {}, case, customer, [], now=NOW)
    assert result["passed"] is False
    assert result["action"] == "send_reminder"
    assert result["rule"] == "dnd_respected"
    assert result["substituted"] is True


def test_calling_hours_blocks_voice_call_outside_window():
    case = make_case(root_cause="overdue_late")
    late_night_ist = datetime(2026, 8, 23, 22, 0, tzinfo=timezone.utc)  # ~3:30am IST
    result = check_compliance("voice_call", {}, case, make_customer(), [], now=late_night_ist)
    assert result["passed"] is False
    assert result["rule"] == "calling_hours"
    assert result["action"] == "send_reminder"


def test_calling_hours_allows_voice_call_inside_window():
    case = make_case(root_cause="overdue_late")
    result = check_compliance("voice_call", {}, case, make_customer(dnd_registered=False), [], now=NOW)
    assert result["passed"] is True
    assert result["action"] == "voice_call"


def test_same_channel_cooldown_blocks_repeat_within_24h():
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(preferred_channel="email")
    attempts = [make_attempt(action="send_reminder", channel="email_link", timestamp=NOW - timedelta(hours=5))]
    result = check_compliance("send_reminder", {}, case, customer, attempts, now=NOW)
    assert result["passed"] is False
    assert result["rule"] == "same_channel_24h_cooldown"


def test_same_channel_cooldown_allows_after_24h():
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(preferred_channel="email")
    attempts = [make_attempt(action="send_reminder", channel="email_link", timestamp=NOW - timedelta(hours=30))]
    result = check_compliance("send_reminder", {}, case, customer, attempts, now=NOW)
    assert result["passed"] is True


def test_retry_spacing_blocks_retry_within_24h():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(action="retry_now", channel="silent_retry", timestamp=NOW - timedelta(hours=10))]
    result = check_compliance("retry_now", {}, case, make_customer(), attempts, now=NOW)
    assert result["passed"] is False
    assert result["rule"] == "retry_spacing_24h"


def test_retry_spacing_allows_retry_after_24h():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(action="retry_now", channel="silent_retry", timestamp=NOW - timedelta(hours=25))]
    result = check_compliance("retry_now", {}, case, make_customer(), attempts, now=NOW)
    assert result["passed"] is True


def test_pre_debit_notice_window_corrects_missing_retry_date():
    case = make_case(root_cause="insufficient_funds")
    result = check_compliance("retry_scheduled", {}, case, make_customer(), [], now=NOW)
    assert result["passed"] is False
    assert result["rule"] == "pre_debit_notice_window"
    assert result["params"]["retry_date"] == NOW + timedelta(hours=24)


def test_pre_debit_notice_window_corrects_too_soon_retry_date():
    case = make_case(root_cause="insufficient_funds")
    result = check_compliance(
        "retry_scheduled", {"retry_date": NOW + timedelta(hours=2)}, case, make_customer(), [], now=NOW
    )
    assert result["passed"] is False
    assert result["rule"] == "pre_debit_notice_window"


def test_pre_debit_notice_window_passes_with_sufficient_lead_time():
    case = make_case(root_cause="insufficient_funds")
    result = check_compliance(
        "retry_scheduled", {"retry_date": NOW + timedelta(hours=48)}, case, make_customer(), [], now=NOW
    )
    assert result["passed"] is True
    assert result["params"]["retry_date"] == NOW + timedelta(hours=48)


def test_opt_out_blocks_further_contact_in_compliance_layer_too():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(outcome="opt_out")]
    result = check_compliance("send_reminder", {}, case, make_customer(), attempts, now=NOW)
    assert result["passed"] is False
    assert result["rule"] == "opt_out_honored"


def test_opt_out_still_allows_no_action():
    case = make_case(root_cause="insufficient_funds")
    attempts = [make_attempt(outcome="opt_out")]
    result = check_compliance("no_action", {}, case, make_customer(), attempts, now=NOW)
    assert result["passed"] is True
