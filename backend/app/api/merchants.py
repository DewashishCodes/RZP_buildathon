from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Merchant

from .schemas import MerchantOut

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("", response_model=list[MerchantOut])
def list_merchants(db: Session = Depends(get_db)):
    return db.execute(select(Merchant).order_by(Merchant.name)).scalars().all()
