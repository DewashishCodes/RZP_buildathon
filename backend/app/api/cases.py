import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit.timeline import get_case_timeline, list_cases, list_scheduled_cases
from app.constants import CASE_STATUSES, CASE_TYPES
from app.db.session import get_db

from .schemas import CaseOut, CaseTimelineResponse

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseOut])
def list_cases_route(
    batch_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    status: str | None = None,
    type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    # Validate filters against the taxonomy instead of silently returning
    # an empty list for a typo'd value ("recoveredd" should be a 400, not
    # a confusing zero rows).
    if status is not None and status not in CASE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(CASE_STATUSES)}")
    if type is not None and type not in CASE_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of: {', '.join(CASE_TYPES)}")
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
