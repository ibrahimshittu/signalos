"""Persist hash-bound reviews and explicit user execution actions.

Revision ID: 20260815_0010
Revises: 20260815_0009
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0010"
down_revision: str | None = "20260815_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_indexes(table: str, columns: Sequence[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "execution_action_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("action_hash", sa.String(64), nullable=False),
        sa.Column("terms", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes(
        "execution_action_reviews",
        ("action_type", "created_at", "expires_at", "target_id", "user_id"),
    )

    op.create_table(
        "execution_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "review_id",
            sa.String(36),
            sa.ForeignKey("execution_action_reviews.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("broker_order_link_id", sa.String(36)),
        sa.Column("broker_order_id", sa.String(100)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", name="uq_execution_actions_review"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_execution_actions_user_idempotency"
        ),
        sa.UniqueConstraint("broker_order_link_id", name="uq_execution_actions_order_link_id"),
    )
    _create_indexes(
        "execution_actions",
        (
            "action_type",
            "broker_order_id",
            "connection_id",
            "created_at",
            "state",
            "target_id",
            "updated_at",
            "user_id",
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "execution_action_reviews" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "execution_actions" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("execution_actions")
    op.drop_table("execution_action_reviews")
