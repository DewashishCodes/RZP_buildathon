"""Phase 9 seed-guarantee: the four hand-crafted scenarios in
guaranteed_cases.py that are supposed to be fully deterministic (no LLM
involved) must actually trip check_stopping_rules on their very first
round. This is what "guaranteed" means - if these ever stop firing, the
batch dashboard could go a whole demo without ever showing a guardrail
overriding anything.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.detection.receivables import classify_receivable
from app.detection.rules import classify_by_rules
from app.policy.guardrails import check_stopping_rules
from app.simulation.guaranteed_cases import build_guaranteed_cases

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _customer_by_id(customers, customer_id):
    return next(c for c in customers if c["id"] == customer_id)


def _classify(case: dict) -> str:
    if case["type"] == "receivable":
        ns = SimpleNamespace(disputed=case["disputed"], due_at=case["due_at"])
        return classify_receivable(ns, now=NOW)
    rule = classify_by_rules(case["raw_failure_reason"] or "")
    assert rule is not None, "guaranteed payment cases must classify deterministically via rules, no LLM"
    return rule


def _as_namespace(case: dict, root_cause: str):
    return SimpleNamespace(id=case["id"], root_cause=root_cause, created_at=case["created_at"])


def _attempts_for(attempts: list[dict], case_id):
    return [
        SimpleNamespace(action=a["action"], channel=a["channel"], outcome=a["outcome"], timestamp=a["timestamp"])
        for a in attempts
        if a["case_id"] == case_id
    ]


def test_build_guaranteed_cases_returns_six_scenarios():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    assert len(customers) == len(cases) == 6


def test_fraud_case_auto_escalates():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    case = cases[0]
    root_cause = _classify(case)
    assert root_cause == "fraud_suspected"
    result = check_stopping_rules(_as_namespace(case, root_cause), None, [], now=NOW)
    assert result is not None
    assert result["action"] == "escalate_human"
    assert result["rule"] == "fraud_or_dispute_auto_escalate"


def test_disputed_receivable_auto_escalates():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    case = cases[1]
    assert case["disputed"] is True
    root_cause = _classify(case)
    assert root_cause == "disputed"
    result = check_stopping_rules(_as_namespace(case, root_cause), None, [], now=NOW)
    assert result is not None
    assert result["action"] == "escalate_human"
    assert result["rule"] == "fraud_or_dispute_auto_escalate"


def test_exhausted_contacts_case_hits_max_total_contacts():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    case = cases[2]
    root_cause = _classify(case)
    case_attempts = _attempts_for(attempts, case["id"])
    assert len(case_attempts) == 4
    result = check_stopping_rules(_as_namespace(case, root_cause), None, case_attempts, now=NOW)
    assert result is not None
    assert result["action"] == "escalate_human"
    assert result["rule"] == "max_total_contacts"


def test_stale_case_hits_case_age_exceeded():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    case = cases[3]
    root_cause = _classify(case)
    result = check_stopping_rules(_as_namespace(case, root_cause), None, [], now=NOW)
    assert result is not None
    assert result["action"] == "escalate_human"
    assert result["rule"] == "case_age_exceeded"


def test_dnd_bias_case_is_dnd_registered_receivable_with_prior_contact():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    case = cases[4]
    customer = _customer_by_id(customers, case["customer_id"])
    assert customer["dnd_registered"] is True
    assert case["type"] == "receivable"
    root_cause = _classify(case)
    assert root_cause == "overdue_late"
    assert len(_attempts_for(attempts, case["id"])) == 1


def test_promise_to_pay_bias_case_is_cooperative_mid_overdue_receivable():
    customers, cases, attempts = build_guaranteed_cases(now=NOW)
    case = cases[5]
    customer = _customer_by_id(customers, case["customer_id"])
    assert customer["responsiveness_profile"] == "cooperative"
    root_cause = _classify(case)
    assert root_cause == "overdue_mid"
