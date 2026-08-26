"""Opt-in per-merchant API-key auth. REQUIRE_MERCHANT_API_KEY defaults to
false - this project deliberately has no auth wall by default (see
CLAUDE.md's multi-tenancy notes) to keep judge/demo access frictionless.
When turned on, mutating routes that accept a merchant_id check it
against that merchant's Merchant.api_key via the X-API-Key header.

A plain function rather than a FastAPI Depends, since the routes that
need this take merchant_id from different places (request body vs query
param) - calling it explicitly at the top of the route body is simpler
than reshaping each route's dependency signature to match.
"""
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Merchant


def verify_merchant_api_key(db: Session, merchant_id: uuid.UUID, x_api_key: str | None) -> None:
    if not settings.require_merchant_api_key:
        return
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or not merchant.api_key or x_api_key != merchant.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key for this merchant.")
