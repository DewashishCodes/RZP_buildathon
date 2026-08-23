from app.constants import CARD_ON_FILE_STATUSES, CASE_TYPES, PREFERRED_CHANNELS, RESPONSIVENESS_PROFILES
from app.simulation.generator import generate_batch


def test_generate_batch_shapes():
    customers, cases = generate_batch(n_cases=300, seed=1)

    assert len(customers) == 300
    assert len(cases) == 300

    case_ids = {c["id"] for c in cases}
    assert len(case_ids) == 300  # all unique

    for customer in customers:
        assert customer["responsiveness_profile"] in RESPONSIVENESS_PROFILES
        assert customer["preferred_channel"] in PREFERRED_CHANNELS
        assert customer["card_on_file_status"] in CARD_ON_FILE_STATUSES
        assert isinstance(customer["dnd_registered"], bool)

    for case in cases:
        assert case["type"] in CASE_TYPES
        assert case["amount"] > 0
        assert case["currency"] == "INR"
        assert case["status"] == "open"
        assert case["root_cause"] is None  # filled by detection layer, not the generator
        assert case["outcome"] == "pending"


def test_generate_batch_is_reproducible_with_seed():
    _, cases_a = generate_batch(n_cases=100, seed=42)
    _, cases_b = generate_batch(n_cases=100, seed=42)

    types_a = [c["type"] for c in cases_a]
    types_b = [c["type"] for c in cases_b]
    assert types_a == types_b


def test_generate_batch_type_distribution_roughly_matches_weights():
    _, cases = generate_batch(n_cases=2000, seed=7)
    counts = {t: 0 for t in CASE_TYPES}
    for case in cases:
        counts[case["type"]] += 1

    # payment_failure weighted ~0.55, mandate_failure ~0.15, receivable ~0.30
    assert 0.45 < counts["payment_failure"] / 2000 < 0.65
    assert 0.08 < counts["mandate_failure"] / 2000 < 0.22
    assert 0.20 < counts["receivable"] / 2000 < 0.40


def test_receivable_cases_have_due_at_and_no_failure_reason():
    _, cases = generate_batch(n_cases=500, seed=3)
    receivables = [c for c in cases if c["type"] == "receivable"]
    assert receivables
    for case in receivables:
        assert case["due_at"] is not None
        assert case["raw_failure_reason"] is None


def test_payment_and_mandate_cases_have_failure_reason_and_no_due_at():
    _, cases = generate_batch(n_cases=500, seed=4)
    non_receivables = [c for c in cases if c["type"] != "receivable"]
    assert non_receivables
    for case in non_receivables:
        assert case["due_at"] is None
        assert case["raw_failure_reason"]
