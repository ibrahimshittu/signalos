"""Derive sizing capital from synchronized broker equity.

Revision ID: 20260815_0014
Revises: 20260815_0013
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0014"
down_revision: str | None = "20260815_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("investment_profiles") as batch:
        batch.alter_column(
            "intended_capital",
            existing_type=sa.Numeric(24, 8),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE investment_profiles SET intended_capital = 1 "
        "WHERE intended_capital IS NULL"
    )
    with op.batch_alter_table("investment_profiles") as batch:
        batch.alter_column(
            "intended_capital",
            existing_type=sa.Numeric(24, 8),
            nullable=False,
        )
