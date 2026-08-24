"""CLI: generate a synthetic batch and persist it to Postgres.

Usage:
    python -m app.simulation.seed --n 200 --seed 42
"""
import argparse
import uuid
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models import Attempt, Case, Customer
from app.simulation.generator import generate_batch
from app.simulation.guaranteed_cases import build_guaranteed_cases
from app.simulation.merchants import seed_merchants


def seed_batch(
    n_cases: int = 200,
    seed: int | None = None,
    merchant_id: uuid.UUID | None = None,
    include_guaranteed: bool = True,
) -> tuple[int, int, uuid.UUID]:
    """Returns (n_customers, n_cases, batch_id). Every case gets tagged
    with the same fresh batch_id so it's drillable via the Phase 7
    rollup queries (app/audit/rollup.py) scoped to just this run.

    merchant_id defaults to the first demo merchant (auto-seeded if
    missing) so CLI usage keeps working without callers having to look
    one up first - the API route requires it explicitly instead.

    include_guaranteed=True (default) adds the fixed set of hand-crafted
    scenario cases from guaranteed_cases.py on top of the n_cases random
    ones, so every batch - even a small demo-sized one - is certain to
    contain a guardrail-fired case, a compliance-substitution case, etc.
    (PRD §16). Set False for callers that want a purely random batch
    (e.g. statistical tests over the generator itself).
    """
    batch_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    customers, cases = generate_batch(n_cases=n_cases, seed=seed)
    attempts: list[dict] = []
    if include_guaranteed:
        g_customers, g_cases, g_attempts = build_guaranteed_cases(now=now)
        customers += g_customers
        cases += g_cases
        attempts += g_attempts

    db = SessionLocal()
    try:
        if merchant_id is None:
            merchant_id = seed_merchants(db)[0].id
        for case in cases:
            case["batch_id"] = batch_id
            case["merchant_id"] = merchant_id

        db.bulk_insert_mappings(Customer, customers)
        db.bulk_insert_mappings(Case, cases)
        if attempts:
            db.bulk_insert_mappings(Attempt, attempts)
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
