"""CLI: run the full detection -> policy -> execution pipeline over every
open payment_failure/mandate_failure case in the DB, and print the batch
summary (Phase 4 manual walkthrough - the first full end-to-end run).

Usage:
    python scripts/run_batch.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.execution.runner import run_batch


def main() -> None:
    db = SessionLocal()
    try:
        summary = run_batch(db)
        print("Batch run complete.\n")
        print(f"Cases processed:  {summary['total_cases']}")
        print(f"Rs. at risk:      {summary['total_at_risk']:,.2f}")
        print(f"Rs. recovered:    {summary['total_recovered']:,.2f}")
        print(f"Recovery rate:    {summary['recovery_rate'] * 100:.1f}%")
        print("\nStatus breakdown:")
        for status, count in sorted(summary["status_counts"].items()):
            print(f"  {status:18s} {count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
