"""audit_events timestamp uses server-side clock_timestamp

Revision ID: bbfc977fd9d1
Revises: 05280d324a02
Create Date: 2026-08-23 13:16:56.404172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbfc977fd9d1'
down_revision: Union[str, None] = '05280d324a02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "audit_events",
        "timestamp",
        server_default=sa.text("clock_timestamp()"),
    )


def downgrade() -> None:
    op.alter_column(
        "audit_events",
        "timestamp",
        server_default=None,
    )
