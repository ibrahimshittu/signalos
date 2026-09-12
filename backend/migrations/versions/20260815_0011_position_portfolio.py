"""Track fresh position portfolios and support portfolio-margin accounts.

Revision ID: 20260815_0011
Revises: 20260815_0010
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0011"
down_revision: str | None = "20260815_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("broker_positions") as batch:
        batch.alter_column(
            "leverage",
            existing_type=sa.Numeric(12, 4),
            nullable=True,
        )
    op.create_table(
        "broker_reconciliation_checkpoints",
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("positions_reconciled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_broker_reconciliation_checkpoints_positions_reconciled_at",
        "broker_reconciliation_checkpoints",
        ["positions_reconciled_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "broker_reconciliation_checkpoints" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("broker_reconciliation_checkpoints")
    op.execute("UPDATE broker_positions SET leverage = 1 WHERE leverage IS NULL")
    with op.batch_alter_table("broker_positions") as batch:
        batch.alter_column(
            "leverage",
            existing_type=sa.Numeric(12, 4),
            nullable=False,
        )
