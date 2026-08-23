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

    n_customers, n_cases, batch_id = seed_batch(n_cases=25, seed=99)
    assert n_customers == 25
    assert n_cases == 25
    assert batch_id is not None

    db = SessionLocal()
    try:
        after_customers = db.scalar(select(func.count()).select_from(Customer)) or 0
        after_cases = db.scalar(select(func.count()).select_from(Case)) or 0
    finally:
        db.close()

    assert after_customers == before_customers + 25
    assert after_cases == before_cases + 25


def test_seed_batch_tags_all_cases_with_same_batch_id():
    _, _, batch_id = seed_batch(n_cases=10, seed=101)

    db = SessionLocal()
    try:
        batch_ids = db.scalars(select(Case.batch_id).where(Case.batch_id == batch_id)).all()
    finally:
        db.close()

    assert len(batch_ids) == 10
    assert all(bid == batch_id for bid in batch_ids)
