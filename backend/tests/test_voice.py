from datetime import datetime, timedelta
from types import SimpleNamespace

from app.execution.voice import (
    FALLBACK_EXTRACTION,
    MAX_TURNS,
    extract_outcome,
    format_transcript_for_storage,
    run_conversation,
)
from tests.fakes import FakeAPIError, FakeGeminiClient

NOW = datetime(2026, 8, 23, 12, 0)


def make_case():
    return SimpleNamespace(type="payment_failure", root_cause="insufficient_funds", amount=1800)


def make_customer(profile="cooperative"):
    return SimpleNamespace(responsiveness_profile=profile)


def test_run_conversation_produces_max_turns_alternating_roles():
    client = FakeGeminiClient(response_text="Namaste, aapka payment fail ho gaya tha.")
    turns = run_conversation(make_case(), make_customer(), client=client)
    assert len(turns) == MAX_TURNS
    assert [t["role"] for t in turns] == ["agent", "customer", "agent", "customer", "agent", "customer"]
    assert len(client.calls) == MAX_TURNS


def test_run_conversation_fails_safe_on_api_error():
    client = FakeGeminiClient(raise_error=FakeAPIError())
    turns = run_conversation(make_case(), make_customer(), client=client)
    assert len(turns) == 1
    assert turns[0]["role"] == "agent"


def test_format_transcript_for_storage_includes_all_turns():
    turns = [{"role": "agent", "text": "Hello"}, {"role": "customer", "text": "Haan bolo"}]
    text = format_transcript_for_storage(turns)
    assert "Agent: Hello" in text
    assert "Customer: Haan bolo" in text


def test_extract_outcome_parses_valid_consent_json():
    client = FakeGeminiClient(
        response_text='{"consent": true, "action": "retry_now", "promise_to_pay_date_offset_days": 0}'
    )
    result = extract_outcome([{"role": "customer", "text": "haan retry kar do"}], client=client, now=NOW)
    assert result == {"consent": True, "action": "retry_now", "promise_to_pay_date": None}


def test_extract_outcome_parses_promise_to_pay_with_date():
    client = FakeGeminiClient(
        response_text='{"consent": true, "action": "promise_to_pay", "promise_to_pay_date_offset_days": 7}'
    )
    result = extract_outcome([], client=client, now=NOW)
    assert result["consent"] is True
    assert result["action"] == "promise_to_pay"
    assert result["promise_to_pay_date"] == (NOW + timedelta(days=7)).date()


def test_extract_outcome_falls_back_on_malformed_json():
    client = FakeGeminiClient(response_text="not json")
    result = extract_outcome([], client=client, now=NOW)
    assert result == FALLBACK_EXTRACTION


def test_extract_outcome_falls_back_on_api_error():
    client = FakeGeminiClient(raise_error=FakeAPIError())
    result = extract_outcome([], client=client, now=NOW)
    assert result == FALLBACK_EXTRACTION


def test_extract_outcome_defaults_invalid_action_to_none():
    client = FakeGeminiClient(response_text='{"consent": true, "action": "something_weird"}')
    result = extract_outcome([], client=client, now=NOW)
    assert result["action"] == "none"
    assert result["promise_to_pay_date"] is None
