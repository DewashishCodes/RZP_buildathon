"""add idempotency_key to batch_runs

POST /batches/run accepts an optional idempotency_key; a retried request
with the same (merchant_id, idempotency_key) pair returns the original
batch instead of seeding a duplicate one - see app/api/batches.py.

Revision ID: c4f9a1e2b3d5
Revises: b7e8d2a4c9f1
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f9a1e2b3d5'
down_revision: Union[str, None] = 'b7e8d2a4c9f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('batch_runs', sa.Column('idempotency_key', sa.String(length=200), nullable=True))
    op.create_index(
        'uq_batch_runs_merchant_idempotency_key',
        'batch_runs',
        ['merchant_id', 'idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_batch_runs_merchant_idempotency_key', table_name='batch_runs')
    op.drop_column('batch_runs', 'idempotency_key')
