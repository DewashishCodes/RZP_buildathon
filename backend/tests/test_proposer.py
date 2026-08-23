from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.policy.proposer import FALLBACK_PROPOSAL, propose_action
from tests.fakes import FakeAPIError, FakeGeminiClient

ALLOWED = ["no_action", "retry_now", "retry_scheduled", "send_reminder", "escalate_human", "stop_case"]


def make_case():
    return SimpleNamespace(type="payment_failure", root_cause="insufficient_funds", amount=1500)


def make_customer():
    return SimpleNamespace(responsiveness_profile="cooperative", preferred_channel="sms")


def test_propose_action_parses_valid_json():
    client = FakeGeminiClient(
        response_text='{"action": "retry_scheduled", "params": {"retry_date_offset_hours": 72}, "rationale": "insufficient funds, retry payday-aligned"}'
    )
    result = propose_action(make_case(), make_customer(), [], ALLOWED, client=client)
    assert result["action"] == "retry_scheduled"
    assert result["rationale"]
    expected = datetime.now(timezone.utc) + timedelta(hours=72)
    assert abs((result["params"]["retry_date"] - expected).total_seconds()) < 5


def test_propose_action_falls_back_on_disallowed_action():
    client = FakeGeminiClient(response_text='{"action": "voice_call", "params": {}, "rationale": "not allowed here"}')
    result = propose_action(make_case(), make_customer(), [], ALLOWED, client=client)
    assert result["action"] == FALLBACK_PROPOSAL["action"]


def test_propose_action_falls_back_on_malformed_json():
    client = FakeGeminiClient(response_text="I think we should retry")
    result = propose_action(make_case(), make_customer(), [], ALLOWED, client=client)
    assert result["action"] == FALLBACK_PROPOSAL["action"]


def test_propose_action_defaults_missing_retry_offset():
    client = FakeGeminiClient(response_text='{"action": "retry_scheduled", "params": {}, "rationale": "retry later"}')
    result = propose_action(make_case(), make_customer(), [], ALLOWED, client=client)
    assert result["action"] == "retry_scheduled"
    expected = datetime.now(timezone.utc) + timedelta(hours=72)
    assert abs((result["params"]["retry_date"] - expected).total_seconds()) < 5


def test_propose_action_no_action_has_empty_params():
    client = FakeGeminiClient(response_text='{"action": "no_action", "params": {}, "rationale": "wait"}')
    result = propose_action(make_case(), make_customer(), [], ALLOWED, client=client)
    assert result["action"] == "no_action"
    assert result["params"] == {}


def test_propose_action_falls_back_on_api_error():
    client = FakeGeminiClient(raise_error=FakeAPIError())
    result = propose_action(make_case(), make_customer(), [], ALLOWED, client=client)
    assert result["action"] == FALLBACK_PROPOSAL["action"]
