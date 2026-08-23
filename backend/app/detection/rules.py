"""Deterministic root-cause classification for unambiguous bank/gateway
decline codes (PRD §7). Returns None when no rule matches, signalling the
caller to fall back to the LLM classifier.
"""
import re

# Order matters: first matching pattern wins. Keep specific patterns
# (decline codes) ahead of looser keyword matches.
RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bcode\s*51\b|insufficient funds|\bnsf\b", re.IGNORECASE), "insufficient_funds"),
    (re.compile(r"\bcode\s*54\b|card expired|expired card", re.IGNORECASE), "card_expired"),
    (re.compile(r"\bcode\s*59\b|fraud", re.IGNORECASE), "fraud_suspected"),
    (re.compile(r"\bcode\s*91\b|timeout|unavailable", re.IGNORECASE), "bank_timeout"),
    (re.compile(r"\bmd01\b|mandate revoked|mandate cancelled", re.IGNORECASE), "mandate_revoked"),
    (re.compile(r"\bcode\s*05\b|do not honor|issuer declined", re.IGNORECASE), "issuer_declined"),
]


def classify_by_rules(raw_failure_reason: str) -> str | None:
    if not raw_failure_reason:
        return None
    for pattern, root_cause in RULES:
        if pattern.search(raw_failure_reason):
            return root_cause
    return None
