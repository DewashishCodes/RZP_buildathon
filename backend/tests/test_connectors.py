import random
from datetime import datetime, timezone
from types import SimpleNamespace

from app.execution.connectors import execute_contact_action, execute_voice_call
from tests.fakes import FakeGeminiClient

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def make_case(root_cause="insufficient_funds", amount=1000, case_type="payment_failure"):
    return SimpleNamespace(root_cause=root_cause, amount=amount, type=case_type)


def make_customer(profile="cooperative"):
    return SimpleNamespace(responsiveness_profile=profile)


def test_fraud_suspected_never_recovers_via_connector():
    rng = random.Random(1)
    case = make_case(root_cause="fraud_suspected")
    for _ in range(50):
        result = execute_contact_action(case, make_customer(), "retry_now", now=NOW, rng=rng)
        assert result["recovered"] is False


def test_successful_retry_sets_recovered_amount_to_case_amount():
    rng = random.Random(2)
    case = make_case(root_cause="bank_timeout", amount=2500)  # high base rate, easy to hit a success
    found_success = False
    for _ in range(50):
        result = execute_contact_action(case, make_customer(), "retry_now", now=NOW, rng=rng)
        if result["recovered"]:
            found_success = True
            assert result["recovered_amount"] == 2500.0
            assert result["attempt_outcome"] == "success"
            break
    assert found_success


def test_send_update_link_no_click_is_no_response_not_failure():
    rng = random.Random(3)
    case = make_case(root_cause="card_expired")
    customer = make_customer(profile="hostile")  # low link-click rate
    found_no_response = False
    for _ in range(50):
        result = execute_contact_action(case, customer, "send_update_link", now=NOW, rng=rng)
        if not result["recovered"] and result["attempt_outcome"] == "no_response":
            found_no_response = True
            break
    assert found_no_response


def test_promise_to_pay_outcome_carries_a_date_when_given():
    rng = random.Random(4)
    case = make_case(root_cause="overdue_mid")
    found_promise = False
    for _ in range(50):
        result = execute_contact_action(case, make_customer(), "request_promise_to_pay", now=NOW, rng=rng)
        if result["attempt_outcome"] == "promise_to_pay":
            found_promise = True
            assert result["promise_to_pay_date"] is not None
            break
    assert found_promise


def test_hostile_customers_sometimes_opt_out_on_nudge_channels():
    rng = random.Random(5)
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(profile="hostile")
    outcomes = [execute_contact_action(case, customer, "send_reminder", now=NOW, rng=rng)["attempt_outcome"] for _ in range(200)]
    assert "opt_out" in outcomes


def test_cooperative_customers_never_opt_out():
    rng = random.Random(6)
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(profile="cooperative")
    outcomes = [execute_contact_action(case, customer, "send_reminder", now=NOW, rng=rng)["attempt_outcome"] for _ in range(200)]
    assert "opt_out" not in outcomes


def test_retry_actions_are_never_opted_out_of():
    rng = random.Random(7)
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(profile="hostile")
    outcomes = [execute_contact_action(case, customer, "retry_now", now=NOW, rng=rng)["attempt_outcome"] for _ in range(200)]
    assert "opt_out" not in outcomes


# ---- voice_call connector ----


def test_execute_voice_call_hostile_customer_can_opt_out_without_conversation():
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(profile="hostile")
    client = FakeGeminiClient(response_text='{"consent": false, "action": "none"}')

    found_opt_out = False
    for seed in range(100):
        calls_before = len(client.calls)
        result = execute_voice_call(case, customer, now=NOW, rng=random.Random(seed), llm_client=client)
        if result["attempt_outcome"] == "opt_out":
            found_opt_out = True
            assert result["transcript"] is None
            assert len(client.calls) == calls_before  # no LLM calls made for this opted-out round
            break
    assert found_opt_out


def test_execute_voice_call_no_consent_is_failure_with_transcript():
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(profile="cooperative")  # never opts out
    client = FakeGeminiClient(response_text='{"consent": false, "action": "none"}')

    result = execute_voice_call(case, customer, now=NOW, rng=random.Random(1), llm_client=client)

    assert result["attempt_outcome"] == "failure"
    assert result["recovered"] is False
    assert result["transcript"] is not None
    assert len(client.calls) > 0


def test_execute_voice_call_promise_to_pay_consent_sets_outcome_and_date():
    case = make_case(root_cause="insufficient_funds")
    customer = make_customer(profile="cooperative")
    client = FakeGeminiClient(
        response_text='{"consent": true, "action": "promise_to_pay", "promise_to_pay_date_offset_days": 5}'
    )

    result = execute_voice_call(case, customer, now=NOW, rng=random.Random(2), llm_client=client)

    assert result["attempt_outcome"] == "promise_to_pay"
    assert result["promise_to_pay_date"] is not None
    assert result["transcript"] is not None
