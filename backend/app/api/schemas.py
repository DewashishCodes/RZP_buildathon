"""Pydantic request/response models for the API routes."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel


class MerchantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class RunBatchRequest(BaseModel):
    merchant_id: uuid.UUID
    n_cases: int = 200
    seed: int | None = None
    # False leaves each case's first non-terminal round scheduled
    # (Case.next_action_at) instead of resolving it fully in this call -
    # see app/execution/runner.py and POST /jobs/run-due.
    instant: bool = True


class RunBatchResponse(BaseModel):
    batch_id: uuid.UUID
    n_customers: int
    n_cases: int
    summary: dict


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
