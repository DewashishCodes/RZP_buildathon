"""add missing indexes and server-side timestamp defaults

Two hardening fixes in one revision:

1. Indexes the read paths were missing. attempts.case_id and
   audit_events.case_id back every case drill-down (the timeline queries
   filter on them), audit_events is the highest-volume table, and
   cases.status / cases.created_at back list filters and ordering.

2. Case.created_at and Attempt.timestamp switch from Python-side
   datetime.utcnow() defaults to Postgres now(). utcnow() is deprecated
   since 3.12 and wrote naive datetimes into timezone=True columns;
   AuditEvent.timestamp and Ticket.created_at already use server-side
   defaults for exactly this reason (see bbfc977fd9d1).

Revision ID: a1f2c3d4e5b6
Revises: 171350621f1a
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5b6'
down_revision: Union[str, None] = '171350621f1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_attempts_case_id'), 'attempts', ['case_id'], unique=False)
    op.create_index(op.f('ix_audit_events_case_id'), 'audit_events', ['case_id'], unique=False)
    op.create_index(op.f('ix_audit_events_event_type'), 'audit_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_cases_status'), 'cases', ['status'], unique=False)
    op.create_index(op.f('ix_cases_created_at'), 'cases', ['created_at'], unique=False)

    op.alter_column(
        'cases',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text('now()'),
        nullable=False,
    )
    op.alter_column(
        'attempts',
        'timestamp',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text('now()'),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'attempts',
        'timestamp',
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        nullable=False,
    )
    op.alter_column(
        'cases',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        nullable=False,
    )
    op.drop_index(op.f('ix_cases_created_at'), table_name='cases')
    op.drop_index(op.f('ix_cases_status'), table_name='cases')
    op.drop_index(op.f('ix_audit_events_event_type'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_case_id'), table_name='audit_events')
    op.drop_index(op.f('ix_attempts_case_id'), table_name='attempts')
