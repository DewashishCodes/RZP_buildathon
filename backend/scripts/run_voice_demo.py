"""CLI: run one live voice recovery call for a hand-picked high-value case,
print the full Hinglish transcript turn-by-turn, and the extracted
structured outcome (Phase 5 manual walkthrough - a demo-critical moment).

Creates its own throwaway Customer/Case (does not touch a seeded batch),
runs the real two-role Gemini conversation, then extraction.

Usage:
    python scripts/run_voice_demo.py [cooperative|evasive|unresponsive|hostile]
"""
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.execution import voice


class _Case:
    def __init__(self, type, root_cause, amount):
        self.id = uuid.uuid4()
        self.type = type
        self.root_cause = root_cause
        self.amount = amount


class _Customer:
    def __init__(self, responsiveness_profile):
        self.id = uuid.uuid4()
        self.responsiveness_profile = responsiveness_profile


def main() -> None:
    profile = sys.argv[1] if len(sys.argv) > 1 else "cooperative"
    if profile not in voice.RESPONSIVENESS_BEHAVIOR:
        print(f"Unknown profile '{profile}'. Choose one of: {list(voice.RESPONSIVENESS_BEHAVIOR)}")
        sys.exit(1)

    case = _Case(type="payment_failure", root_cause="insufficient_funds", amount=48500)
    customer = _Customer(responsiveness_profile=profile)

    print(f"=== Voice recovery call: case amount=Rs.{case.amount}, root_cause={case.root_cause}, customer profile={profile} ===\n")

    turns = voice.run_conversation(case, customer)
    for turn in turns:
        speaker = "Recovery Agent" if turn["role"] == "agent" else "Customer"
        print(f"{speaker}: {turn['text']}\n")

    outcome = voice.extract_outcome(turns, now=datetime.now(timezone.utc))
    print("=== Extracted outcome ===")
    print(f"  consent:              {outcome['consent']}")
    print(f"  action:                {outcome['action']}")
    print(f"  promise_to_pay_date:   {outcome['promise_to_pay_date']}")


if __name__ == "__main__":
    main()
