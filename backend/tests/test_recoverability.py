import random

from app.simulation.recoverability import roll_outcome


def test_fraud_suspected_never_recovers():
    rng = random.Random(0)
    for _ in range(200):
        outcome = roll_outcome("fraud_suspected", "retry_now", "cooperative", rng=rng)
        assert outcome["success"] is False
        assert outcome["recovered"] is False


def test_outcome_always_has_success_and_recovered_keys():
    rng = random.Random(1)
    outcome = roll_outcome("insufficient_funds", "retry_scheduled", "cooperative", rng=rng)
    assert "success" in outcome
    assert "recovered" in outcome
    assert isinstance(outcome["success"], bool)


def test_send_update_link_outcome_tracks_link_clicked():
    rng = random.Random(2)
    outcome = roll_outcome("card_expired", "send_update_link", "cooperative", rng=rng)
    assert "link_clicked" in outcome
    if not outcome["link_clicked"]:
        assert outcome["recovered"] is False


def test_promise_to_pay_outcome_tracks_promise_fields():
    rng = random.Random(3)
    outcome = roll_outcome("overdue_mid", "request_promise_to_pay", "cooperative", rng=rng)
    assert "promise_given" in outcome
    if outcome["promise_given"]:
        assert "promise_honored" in outcome
        assert outcome["recovered"] == outcome["promise_honored"]
    else:
        assert outcome["recovered"] is False


def test_cooperative_customers_recover_more_than_hostile_on_aggregate():
    trials = 3000
    rng_coop = random.Random(10)
    rng_hostile = random.Random(10)

    coop_successes = sum(
        roll_outcome("insufficient_funds", "retry_scheduled", "cooperative", rng=rng_coop)["success"]
        for _ in range(trials)
    )
    hostile_successes = sum(
        roll_outcome("insufficient_funds", "retry_scheduled", "hostile", rng=rng_hostile)["success"]
        for _ in range(trials)
    )

    assert coop_successes > hostile_successes


def test_unknown_root_cause_action_pair_uses_default_low_rate():
    rng = random.Random(4)
    successes = sum(
        roll_outcome("issuer_declined", "no_action", "cooperative", rng=rng)["success"] for _ in range(1000)
    )
    # default base rate is 0.05, cooperative multiplier 1.15 => ~5.75%
    assert successes / 1000 < 0.15
