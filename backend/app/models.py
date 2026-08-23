"""SQLAlchemy models: Case, Customer, Attempt, AuditEvent (PRD §6).

`root_cause`, `action`, and `event_type` are stored as plain strings rather
than native Postgres enums. They're validated against the Python enums/lists
in `app/constants.py` at the application layer — this avoids a migration
every time Phase 6 (receivables) or later work adds a new root cause or
action to the bounded action space.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dnd_registered: Mapped[bool] = mapped_column(default=False)
    responsiveness_profile: Mapped[str] = mapped_column(String(20))
    preferred_channel: Mapped[str] = mapped_column(String(20))
    card_on_file_status: Mapped[str] = mapped_column(String(30))

    cases: Mapped[list["Case"]] = relationship(back_populates="customer")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(20))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    raw_failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(50), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), default="pending")
    recovered_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    customer: Mapped["Customer"] = relationship(back_populates="cases")
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="case", order_by="Attempt.timestamp")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="case", order_by="AuditEvent.timestamp")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    channel: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(30))
    compliance_check: Mapped[dict] = mapped_column(JSONB)
    outcome: Mapped[str] = mapped_column(String(20))
    promise_to_pay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transcript: Mapped[str | None] = mapped_column(String, nullable=True)

    case: Mapped["Case"] = relationship(back_populates="attempts")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    event_type: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict] = mapped_column(JSONB)

    case: Mapped["Case"] = relationship(back_populates="audit_events")
