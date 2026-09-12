"""Persist short-lived order reviews and user-confirmed broker submissions.

Revision ID: 20260815_0006
Revises: 20260815_0005
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0006"
down_revision: str | None = "20260815_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_indexes(table: str, columns: Sequence[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "order_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("trade_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proposal_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("order_reviews", ("created_at", "expires_at", "proposal_id", "user_id"))

    op.create_table(
        "broker_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("trade_proposals.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("broker_order_link_id", sa.String(36), nullable=False),
        sa.Column("broker_order_id", sa.String(100)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_broker_orders_user_idempotency"),
        sa.UniqueConstraint("broker_order_link_id", name="uq_broker_orders_order_link_id"),
    )
    _create_indexes(
        "broker_orders",
        (
            "connection_id",
            "created_at",
            "environment",
            "state",
            "updated_at",
            "user_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("broker_orders")
    op.drop_table("order_reviews")
