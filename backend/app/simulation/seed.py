"""CLI: generate a synthetic batch and persist it to Postgres.

Usage:
    python -m app.simulation.seed --n 200 --seed 42
"""
import argparse
import uuid

from app.db.session import SessionLocal
from app.models import Case, Customer
from app.simulation.generator import generate_batch


def seed_batch(n_cases: int = 200, seed: int | None = None) -> tuple[int, int, uuid.UUID]:
    """Returns (n_customers, n_cases, batch_id). Every case gets tagged
    with the same fresh batch_id so it's drillable via the Phase 7
    rollup queries (app/audit/rollup.py) scoped to just this run.
    """
    batch_id = uuid.uuid4()
    customers, cases = generate_batch(n_cases=n_cases, seed=seed)
    for case in cases:
        case["batch_id"] = batch_id

    db = SessionLocal()
    try:
        db.bulk_insert_mappings(Customer, customers)
        db.bulk_insert_mappings(Case, cases)
        db.commit()
    finally:
        db.close()
    return len(customers), len(cases), batch_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a synthetic batch of cases into Postgres")
    parser.add_argument("--n", type=int, default=200, help="number of cases to generate")
    parser.add_argument("--seed", type=int, default=None, help="random seed for reproducibility")
    args = parser.parse_args()

    n_customers, n_cases, batch_id = seed_batch(n_cases=args.n, seed=args.seed)
    print(f"Seeded {n_customers} customers and {n_cases} cases")
    print(f"batch_id: {batch_id}")


if __name__ == "__main__":
    main()
