"""Pydantic request/response models for the API routes."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class MerchantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class RunBatchRequest(BaseModel):
    merchant_id: uuid.UUID
    # Capped server-side: each case fans out to several real Gemini calls,
    # and the pipeline runs synchronously - an uncapped value let one
    # request request 100k cases. (The /run UI already caps at 500; this
    # makes the API stop trusting it.)
    n_cases: int = Field(default=200, ge=1, le=500)
    seed: int | None = None
    # False leaves each case's first non-terminal round scheduled
    # (Case.next_action_at) instead of resolving it fully in this call -
    # see app/execution/runner.py and POST /jobs/run-due.
    instant: bool = True
    # True seeds the batch, returns immediately, and runs the pipeline as a
    # background task - poll GET /batches/{id}/progress. The response's
    # summary is empty in this mode.
    background: bool = False
    # Optional client-supplied dedup key. A retry with the same
    # (merchant_id, idempotency_key) pair returns the original batch
    # instead of seeding a duplicate one - protects against double
    # submission (double-click, retried request after a dropped response).
    idempotency_key: str | None = Field(default=None, max_length=200)


class RunBatchResponse(BaseModel):
    batch_id: uuid.UUID
    n_customers: int
    n_cases: int
    summary: dict


class BatchListItem(BaseModel):
    batch_id: str
    phase: str
    created_at: datetime | None
    total_cases: int
    total_at_risk: float
    total_recovered: float
    recovery_rate: float


class BatchProgressResponse(BaseModel):
    batch_id: str
    # queued | running | complete | failed (complete also for legacy
    # synchronous batches with no batch_runs row).
    phase: str
    total_cases: int
    resolved_cases: int
    recovered_cases: int
    recovered_amount: float
    at_risk_amount: float
    error: str | None = None


class RootCauseBreakdown(BaseModel):
    at_risk: float
    recovered: float
    recovery_rate: float


class BatchSummaryResponse(BaseModel):
    batch_id: str
    total_cases: int
    total_at_risk: float
    total_recovered: float
    recovery_rate: float
    by_root_cause: dict[str, RootCauseBreakdown]
    status_counts: dict[str, int]
    stopping_rule_triggers: int
    compliance_substitutions: int


class AttemptOut(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    channel: str
    action: str
    compliance_check: dict
    outcome: str
    promise_to_pay_date: date | None
    transcript: str | None

    model_config = {"from_attributes": True}


class AuditEventOut(BaseModel):
    id: uuid.UUID
    attempt_id: uuid.UUID | None
    timestamp: datetime
    event_type: str
    actor: str
    payload: dict

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    id: uuid.UUID
    type: str
    customer_id: uuid.UUID
    amount: float
    currency: str
    created_at: datetime
    due_at: datetime | None
    status: str
    raw_failure_reason: str | None
    root_cause: str | None
    outcome: str
    recovered_amount: float
    disputed: bool
    batch_id: uuid.UUID | None
    merchant_id: uuid.UUID | None
    next_action_at: datetime | None

    model_config = {"from_attributes": True}


class CaseTimelineResponse(BaseModel):
    case: CaseOut
    events: list[AuditEventOut]
    attempts: list[AttemptOut]


class TicketOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    merchant_id: uuid.UUID | None
    created_at: datetime
    subject: str
    priority: str
    status: str
    assignee: str
    reason: str

    model_config = {"from_attributes": True}


class RunDueJobsResponse(BaseModel):
    processed: int
    reached_terminal: int
    rescheduled: int
