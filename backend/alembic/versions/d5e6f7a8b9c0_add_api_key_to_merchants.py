"""add api_key to merchants

Opt-in per-merchant auth (REQUIRE_MERCHANT_API_KEY, off by default) -
see app/api/auth.py.

Revision ID: d5e6f7a8b9c0
Revises: c4f9a1e2b3d5
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4f9a1e2b3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('merchants', sa.Column('api_key', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_merchants_api_key', 'merchants', ['api_key'])


def downgrade() -> None:
    op.drop_constraint('uq_merchants_api_key', 'merchants', type_='unique')
    op.drop_column('merchants', 'api_key')
