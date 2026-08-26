"""batch_runs table: lifecycle tracking for background batch runs
(POST /batches/run with background=true returns immediately and the
frontend polls /batches/{id}/progress).

Revision ID: b7e8d2a4c9f1
Revises: a1f2c3d4e5b6
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = 'b7e8d2a4c9f1'
down_revision: Union[str, None] = 'a1f2c3d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'batch_runs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('merchant_id', UUID(), nullable=True),
        sa.Column('requested_cases', sa.Integer(), nullable=False),
        sa.Column('phase', sa.String(length=20), nullable=False),
        sa.Column('error', sa.String(length=1000), nullable=True),
        sa.Column('summary', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_batch_runs_phase'), 'batch_runs', ['phase'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_batch_runs_phase'), table_name='batch_runs')
    op.drop_table('batch_runs')
