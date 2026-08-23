"""Per-case drill-down (PRD §11: "Every case must be drillable to a full
timeline") and the case list/filter query backing GET /cases.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, AuditEvent, Case


def get_case_timeline(db: Session, case_id: uuid.UUID) -> dict | None:
    case = db.get(Case, case_id)
    if case is None:
        return None

    events = (
        db.execute(select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.timestamp))
        .scalars()
        .all()
    )
    attempts = (
        db.execute(select(Attempt).where(Attempt.case_id == case_id).order_by(Attempt.timestamp))
        .scalars()
        .all()
    )

    return {"case": case, "events": events, "attempts": attempts}


def list_cases(
    db: Session,
    batch_id: uuid.UUID | None = None,
    status: str | None = None,
    case_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Case]:
    stmt = select(Case)
    if batch_id is not None:
        stmt = stmt.where(Case.batch_id == batch_id)
    if status is not None:
        stmt = stmt.where(Case.status == status)
    if case_type is not None:
        stmt = stmt.where(Case.type == case_type)
    stmt = stmt.order_by(Case.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())
