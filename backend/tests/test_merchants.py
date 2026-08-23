from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Merchant
from app.simulation.merchants import DEMO_MERCHANTS, seed_merchants


def test_seed_merchants_creates_all_demo_merchants():
    db = SessionLocal()
    try:
        merchants = seed_merchants(db)
        assert len(merchants) == len(DEMO_MERCHANTS)
        slugs = {m.slug for m in merchants}
        assert slugs == {m["slug"] for m in DEMO_MERCHANTS}
    finally:
        db.close()


def test_seed_merchants_is_idempotent():
    db = SessionLocal()
    try:
        seed_merchants(db)
        seed_merchants(db)
        count = db.scalar(select(func.count()).select_from(Merchant))
        assert count == len(DEMO_MERCHANTS)
    finally:
        db.close()
