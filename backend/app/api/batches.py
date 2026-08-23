import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit.rollup import batch_summary
from app.db.session import get_db
from app.execution.runner import run_batch
from app.models import Case, Customer
from app.simulation.generator import generate_batch

from .schemas import BatchSummaryResponse, RunBatchRequest, RunBatchResponse

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("/run", response_model=RunBatchResponse)
def trigger_batch_run(payload: RunBatchRequest, db: Session = Depends(get_db)):
    batch_id = uuid.uuid4()
    customers, cases = generate_batch(n_cases=payload.n_cases, seed=payload.seed)
    for case in cases:
        case["batch_id"] = batch_id
        case["merchant_id"] = payload.merchant_id

    db.bulk_insert_mappings(Customer, customers)
    db.bulk_insert_mappings(Case, cases)
    db.commit()

    case_ids = [case["id"] for case in cases]
    run_batch(db, case_ids=case_ids, instant=payload.instant)

    summary = batch_summary(db, batch_id)
    return RunBatchResponse(
        batch_id=batch_id,
        n_customers=len(customers),
        n_cases=len(cases),
        summary=summary or {},
    )


@router.get("/{batch_id}/summary", response_model=BatchSummaryResponse)
def get_batch_summary(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    summary = batch_summary(db, batch_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return summary
