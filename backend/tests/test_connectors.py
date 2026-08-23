import random
from datetime import datetime, timezone
from types import SimpleNamespace

from app.execution.connectors import execute_contact_action

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def make_case(root_cause="insufficient_funds", amount=1000):
    return SimpleNamespace(root_cause=root_cause, amount=amount)


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
