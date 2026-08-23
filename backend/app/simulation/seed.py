"""CLI: generate a synthetic batch and persist it to Postgres.

Usage:
    python -m app.simulation.seed --n 200 --seed 42
"""
import argparse

from app.db.session import SessionLocal
from app.models import Case, Customer
from app.simulation.generator import generate_batch


def seed_batch(n_cases: int = 200, seed: int | None = None) -> tuple[int, int]:
    customers, cases = generate_batch(n_cases=n_cases, seed=seed)
    db = SessionLocal()
    try:
        db.bulk_insert_mappings(Customer, customers)
        db.bulk_insert_mappings(Case, cases)
        db.commit()
    finally:
        db.close()
    return len(customers), len(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a synthetic batch of cases into Postgres")
    parser.add_argument("--n", type=int, default=200, help="number of cases to generate")
    parser.add_argument("--seed", type=int, default=None, help="random seed for reproducibility")
    args = parser.parse_args()

    n_customers, n_cases = seed_batch(n_cases=args.n, seed=args.seed)
    print(f"Seeded {n_customers} customers and {n_cases} cases")


if __name__ == "__main__":
    main()
