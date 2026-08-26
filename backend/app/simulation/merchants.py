"""Demo tenants. Idempotent seeding (by slug) so it's safe to call on
every app startup / test run without creating duplicates.
"""
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Merchant

DEMO_MERCHANTS = [
    {"slug": "kirana-mart", "name": "Kirana Mart"},
    {"slug": "cloudstack-saas", "name": "CloudStack SaaS"},
    {"slug": "urban-wheels", "name": "Urban Wheels"},
]


def seed_merchants(db: Session) -> list[Merchant]:
    existing = {m.slug: m for m in db.execute(select(Merchant)).scalars().all()}
    created_or_existing = []
    for spec in DEMO_MERCHANTS:
        merchant = existing.get(spec["slug"])
        if merchant is None:
            # Generated even though REQUIRE_MERCHANT_API_KEY defaults off -
            # so a demo can turn auth on later without a backfill step, and
            # scripts/show_merchant_api_keys.py always has something to show.
            merchant = Merchant(id=uuid.uuid4(), name=spec["name"], slug=spec["slug"], api_key=secrets.token_hex(16))
            db.add(merchant)
        created_or_existing.append(merchant)
    db.commit()
    for m in created_or_existing:
        db.refresh(m)
    return created_or_existing
