"""CLI: print a summary of what's currently seeded in Postgres, so a human
can eyeball realism of the synthetic batch (Phase 1 manual walkthrough).

Usage:
    python scripts/inspect_batch.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Case, Customer


def main() -> None:
    db = SessionLocal()
    try:
        total_cases = db.scalar(select(func.count()).select_from(Case)) or 0
        total_customers = db.scalar(select(func.count()).select_from(Customer)) or 0
        print(f"Customers: {total_customers}")
        print(f"Cases: {total_cases}")

        if total_cases == 0:
            print("No cases found — run `python -m app.simulation.seed --n 200` first.")
            return

        print("\nBy case type:")
        for case_type, count, total_amount in db.execute(
            select(Case.type, func.count(), func.sum(Case.amount)).group_by(Case.type)
        ):
            print(f"  {case_type:18s} count={count:4d}  total_amount=Rs.{total_amount:,.2f}")

        print("\nBy customer responsiveness profile:")
        profiles = Counter(db.scalars(select(Customer.responsiveness_profile)))
        for profile, count in profiles.most_common():
            print(f"  {profile:15s} count={count}")

        dnd_count = db.scalar(select(func.count()).select_from(Customer).where(Customer.dnd_registered.is_(True))) or 0
        print(f"\nDND registered customers: {dnd_count} / {total_customers}")

        print("\nSample raw_failure_reason messages:")
        for (msg,) in db.execute(
            select(Case.raw_failure_reason).where(Case.raw_failure_reason.is_not(None)).limit(8)
        ):
            print(f"  - {msg}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
