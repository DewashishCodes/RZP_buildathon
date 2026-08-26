import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.auth import verify_merchant_api_key
from app.db.session import get_db
from app.execution.runner import process_due_cases

from .schemas import RunDueJobsResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/run-due", response_model=RunDueJobsResponse)
def run_due_jobs(
    merchant_id: uuid.UUID | None = None, db: Session = Depends(get_db), x_api_key: str | None = Header(default=None)
):
    """Advances every case currently waiting on a deferred round
    (Case.next_action_at set by a non-instant batch run). Mirrors what a
    real cron/job queue would do on schedule - invoked manually here so a
    demo doesn't have to wait for real wall-clock time to pass.
    """
    # No merchant_id means "every tenant" - auth (when enabled) only
    # applies to a scoped, single-merchant call, since there's no one
    # merchant's key that could authorize the unscoped form.
    if merchant_id is not None:
        verify_merchant_api_key(db, merchant_id, x_api_key)
    return process_due_cases(db, merchant_id=merchant_id)
