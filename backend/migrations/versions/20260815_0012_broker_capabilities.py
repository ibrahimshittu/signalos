"""Persist verified Bybit market trading capabilities.

Revision ID: 20260815_0012
Revises: 20260815_0011
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0012"
down_revision: str | None = "20260815_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "broker_connections",
        sa.Column(
            "spot_trading_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "broker_connections",
        sa.Column(
            "derivatives_trading_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    with op.batch_alter_table("broker_connections") as batch:
        batch.alter_column("spot_trading_enabled", server_default=None)
        batch.alter_column("derivatives_trading_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("broker_connections", "derivatives_trading_enabled")
    op.drop_column("broker_connections", "spot_trading_enabled")
