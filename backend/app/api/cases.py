import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit.timeline import get_case_timeline, list_cases, list_scheduled_cases
from app.db.session import get_db

from .schemas import CaseOut, CaseTimelineResponse

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
def list_cases_route(
    batch_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    status: str | None = None,
    type: str | None = Query(default=None, alias="type"),
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return list_cases(
        db, batch_id=batch_id, merchant_id=merchant_id, status=status, case_type=type, limit=limit, offset=offset
    )


# Declared before /{case_id} - a literal path must be registered ahead of
# the parameterized one or route matching would be ambiguous.
@router.get("/scheduled", response_model=list[CaseOut])
def list_scheduled_cases_route(merchant_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    return list_scheduled_cases(db, merchant_id=merchant_id)


@router.get("/{case_id}", response_model=CaseTimelineResponse)
def get_case_route(case_id: uuid.UUID, db: Session = Depends(get_db)):
    timeline = get_case_timeline(db, case_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return timeline
