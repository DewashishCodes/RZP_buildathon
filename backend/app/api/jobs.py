import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.execution.runner import process_due_cases

from .schemas import RunDueJobsResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/run-due", response_model=RunDueJobsResponse)
def run_due_jobs(merchant_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    """Advances every case currently waiting on a deferred round
    (Case.next_action_at set by a non-instant batch run). Mirrors what a
    real cron/job queue would do on schedule - invoked manually here so a
    demo doesn't have to wait for real wall-clock time to pass.
    """
    return process_due_cases(db, merchant_id=merchant_id)
