"""CLI: print each demo merchant's slug + api_key, for testing
REQUIRE_MERCHANT_API_KEY locally (the key is never returned by GET
/merchants, since that's an open endpoint).

Usage:
    python scripts/show_merchant_api_keys.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.simulation.merchants import seed_merchants


def main() -> None:
    db = SessionLocal()
    try:
        for merchant in seed_merchants(db):
            print(f"{merchant.slug:20s} {merchant.name:20s} {merchant.api_key}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
