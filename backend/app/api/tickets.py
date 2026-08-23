import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Ticket

from .schemas import TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    merchant_id: uuid.UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Ticket)
    if merchant_id is not None:
        stmt = stmt.where(Ticket.merchant_id == merchant_id)
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    stmt = stmt.order_by(Ticket.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
