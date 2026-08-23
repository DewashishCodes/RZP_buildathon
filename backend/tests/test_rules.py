from app.detection.rules import classify_by_rules


def test_insufficient_funds_variants():
    assert classify_by_rules("NSF: Insufficient funds in account") == "insufficient_funds"
    assert classify_by_rules("Decline code 51: insufficient funds") == "insufficient_funds"


def test_card_expired_variants():
    assert classify_by_rules("Card expired") == "card_expired"
    assert classify_by_rules("Decline code 54: expired card") == "card_expired"


def test_issuer_declined_variants():
    assert classify_by_rules("Issuer declined the transaction") == "issuer_declined"
    assert classify_by_rules("Decline code 05: do not honor") == "issuer_declined"


def test_bank_timeout_variants():
    assert classify_by_rules("Bank timeout - no response from issuer") == "bank_timeout"
    assert classify_by_rules("Decline code 91: issuer unavailable") == "bank_timeout"


def test_fraud_suspected_variants():
    assert classify_by_rules("Suspected fraud - transaction blocked") == "fraud_suspected"
    assert classify_by_rules("Decline code 59: suspected fraud") == "fraud_suspected"


def test_mandate_revoked_variants():
    assert classify_by_rules("Mandate revoked by customer") == "mandate_revoked"
    assert classify_by_rules("NACH return code MD01: mandate cancelled") == "mandate_revoked"


def test_ambiguous_message_returns_none():
    assert classify_by_rules("Transaction could not be completed. Please contact your bank.") is None
    assert classify_by_rules("Payment failed. Reason not specified by processor.") is None
    assert classify_by_rules("Debit unsuccessful, generic decline.") is None


def test_empty_message_returns_none():
    assert classify_by_rules("") is None
    assert classify_by_rules(None) is None
