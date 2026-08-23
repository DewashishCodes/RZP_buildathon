from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Case, Customer
from app.simulation.seed import seed_batch


def test_seed_batch_writes_expected_row_counts():
    db = SessionLocal()
    try:
        before_customers = db.scalar(select(func.count()).select_from(Customer)) or 0
        before_cases = db.scalar(select(func.count()).select_from(Case)) or 0
    finally:
        db.close()

    n_customers, n_cases = seed_batch(n_cases=25, seed=99)
    assert n_customers == 25
    assert n_cases == 25

    db = SessionLocal()
    try:
        after_customers = db.scalar(select(func.count()).select_from(Customer)) or 0
        after_cases = db.scalar(select(func.count()).select_from(Case)) or 0
    finally:
        db.close()

    assert after_customers == before_customers + 25
    assert after_cases == before_cases + 25
