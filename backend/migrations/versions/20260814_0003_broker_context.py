"""Add the isolated active broker context.

Revision ID: 20260814_0003
Revises: 20260814_0002
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0003"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_contexts",
        sa.Column("user_id", sa.String(200), primary_key=True),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("switched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_broker_contexts_environment", "broker_contexts", ["environment"])
    op.create_index(
        "ix_broker_contexts_connection_id",
        "broker_contexts",
        ["connection_id"],
        unique=True,
    )
    op.create_index("ix_broker_contexts_switched_at", "broker_contexts", ["switched_at"])


def downgrade() -> None:
    op.drop_table("broker_contexts")
