import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.rollup import batch_summary, guardrail_interventions, list_batches, recovery_curve
from app.db.session import SessionLocal, get_db
from app.execution.runner import TERMINAL_STATUSES, run_batch
from app.models import Attempt, BatchRun, Case, Customer
from app.simulation.generator import generate_batch
from app.simulation.guaranteed_cases import build_guaranteed_cases

from .schemas import (
    BatchListItem,
    BatchProgressResponse,
    BatchSummaryResponse,
    RunBatchRequest,
    RunBatchResponse,
)

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("", response_model=list[BatchListItem])
def list_batch_runs(merchant_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    return list_batches(db, merchant_id=merchant_id)


@router.post("/run", response_model=RunBatchResponse)
def trigger_batch_run(payload: RunBatchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    batch_id = uuid.uuid4()
    customers, cases = generate_batch(n_cases=payload.n_cases, seed=payload.seed)
    # Hand-crafted scenario cases (PRD §16: guardrail-fired, compliance-
    # substitution, etc. must not be left to chance) - see
    # app/simulation/guaranteed_cases.py.
    g_customers, g_cases, g_attempts = build_guaranteed_cases()
    customers += g_customers
    cases += g_cases
    for case in cases:
        case["batch_id"] = batch_id
        case["merchant_id"] = payload.merchant_id

    if payload.background:
        db.bulk_insert_mappings(
            BatchRun, [{"id": batch_id, "merchant_id": payload.merchant_id, "requested_cases": len(cases), "phase": "queued"}]
        )
    db.bulk_insert_mappings(Customer, customers)
    db.bulk_insert_mappings(Case, cases)
    if g_attempts:
        db.bulk_insert_mappings(Attempt, g_attempts)
    db.commit()

    case_ids = [case["id"] for case in cases]
    if payload.background:
        # The seed rows are committed above, so the pipeline runs entirely
        # outside the request; /batches/{id}/progress reports on it. A new
        # session is required - the request's session closes with the call.
        background_tasks.add_task(_execute_background_batch, batch_id, case_ids, payload.instant)
        return RunBatchResponse(batch_id=batch_id, n_customers=len(customers), n_cases=len(cases), summary={})

    run_batch(db, case_ids=case_ids, instant=payload.instant)
    summary = batch_summary(db, batch_id)
    return RunBatchResponse(
        batch_id=batch_id,
        n_customers=len(customers),
        n_cases=len(cases),
        summary=summary or {},
    )


def _execute_background_batch(batch_id: uuid.UUID, case_ids: list[uuid.UUID], instant: bool) -> None:
    """Background-task entry point. Owns its own DB session and flips the
    BatchRun row queued -> running -> complete|failed. Any exception is
    captured on the row rather than lost in a detached thread."""
    db = SessionLocal()
    try:
        run = db.get(BatchRun, batch_id)
        if run is not None:
            run.phase = "running"
            db.commit()

        run_batch(db, case_ids=case_ids, instant=instant)
        summary = batch_summary(db, batch_id)

        run = db.get(BatchRun, batch_id)
        if run is not None:
            run.phase = "complete"
            run.summary = summary or {}
            db.commit()
    except Exception as exc:  # noqa: BLE001 - surfaced via the batch row
        db.rollback()
        run = db.get(BatchRun, batch_id)
        if run is not None:
            run.phase = "failed"
            run.error = f"{type(exc).__name__}: {exc}"[:1000]
            db.commit()
    finally:
        db.close()


@router.get("/{batch_id}/progress", response_model=BatchProgressResponse)
def get_batch_progress(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(BatchRun, batch_id)

    total = db.scalar(select(func.count()).select_from(Case).where(Case.batch_id == batch_id))
    if total is None or total == 0:
        raise HTTPException(status_code=404, detail="Batch not found")

    resolved = db.scalar(
        select(func.count()).select_from(Case).where(Case.batch_id == batch_id, Case.status.in_(TERMINAL_STATUSES))
    )
    # ₹ at risk spans every case in the batch; recovered figures only the
    # ones that actually recovered.
    at_risk_amount = db.scalar(select(func.coalesce(func.sum(Case.amount), 0)).where(Case.batch_id == batch_id))
    recovered_count, recovered_amount = db.execute(
        select(func.count(), func.coalesce(func.sum(Case.recovered_amount), 0)).where(
            Case.batch_id == batch_id, Case.status == "recovered"
        )
    ).one()
    # Legacy synchronous batches have no BatchRun row; their pipeline always
    # finished inside the request that created them.
    phase = run.phase if run is not None else "complete"

    return BatchProgressResponse(
        batch_id=str(batch_id),
        phase=phase,
        total_cases=total,
        resolved_cases=resolved or 0,
        recovered_cases=recovered_count or 0,
        recovered_amount=float(recovered_amount or 0),
        at_risk_amount=float(at_risk_amount or 0),
        error=run.error if run is not None else None,
    )


@router.get("/{batch_id}/guardrails")
def get_batch_guardrails(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Case).where(Case.batch_id == batch_id))
    if not total:
        raise HTTPException(status_code=404, detail="Batch not found")
    return guardrail_interventions(db, batch_id)


@router.get("/{batch_id}/curve")
def get_batch_recovery_curve(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Case).where(Case.batch_id == batch_id))
    if not total:
        raise HTTPException(status_code=404, detail="Batch not found")
    return recovery_curve(db, batch_id)


@router.get("/{batch_id}/summary", response_model=BatchSummaryResponse)
def get_batch_summary(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    summary = batch_summary(db, batch_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return summary
