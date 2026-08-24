from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Case, Customer
from app.simulation.guaranteed_cases import build_guaranteed_cases
from app.simulation.seed import seed_batch

N_GUARANTEED_CASES = len(build_guaranteed_cases()[1])


def test_seed_batch_writes_expected_row_counts_without_guaranteed_cases():
    db = SessionLocal()
    try:
        before_customers = db.scalar(select(func.count()).select_from(Customer)) or 0
        before_cases = db.scalar(select(func.count()).select_from(Case)) or 0
    finally:
        db.close()

    n_customers, n_cases, batch_id = seed_batch(n_cases=25, seed=99, include_guaranteed=False)
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


def test_seed_batch_includes_guaranteed_cases_by_default():
    n_customers, n_cases, batch_id = seed_batch(n_cases=10, seed=102)

    assert n_customers == 10 + N_GUARANTEED_CASES
    assert n_cases == 10 + N_GUARANTEED_CASES

    db = SessionLocal()
    try:
        batch_ids = db.scalars(select(Case.batch_id).where(Case.batch_id == batch_id)).all()
    finally:
        db.close()

    assert len(batch_ids) == 10 + N_GUARANTEED_CASES


def test_seed_batch_tags_all_cases_with_same_batch_id():
    _, n_cases, batch_id = seed_batch(n_cases=10, seed=101, include_guaranteed=False)

    db = SessionLocal()
    try:
        batch_ids = db.scalars(select(Case.batch_id).where(Case.batch_id == batch_id)).all()
    finally:
        db.close()

    assert len(batch_ids) == 10
    assert all(bid == batch_id for bid in batch_ids)
