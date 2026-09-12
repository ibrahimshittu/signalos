"""Remove execution authority and retain read-only advisory records.

Revision ID: 20260815_0004
Revises: 20260814_0003
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0004"
down_revision: str | None = "20260814_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM broker_credentials WHERE purpose = 'trading'"))
    op.execute(
        sa.text(
            "UPDATE trade_proposals SET status = CASE "
            "WHEN status = 'awaiting_confirmation' THEN 'available' "
            "WHEN status = 'revalidation_failed' THEN 'invalidated' "
            "ELSE 'archived' END "
            "WHERE status NOT IN ('available', 'rejected', 'expired', 'invalidated', 'archived')"
        )
    )
    op.drop_table("execution_intents")
    op.drop_table("trade_approvals")


def downgrade() -> None:
    op.create_table(
        "trade_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("trade_proposals.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("proposal_hash", sa.String(64), nullable=False),
        sa.Column("challenge_id", sa.String(200), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trade_approvals_user_id", "trade_approvals", ["user_id"])

    op.create_table(
        "execution_intents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("trade_proposals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("proposal_id", name="uq_execution_intents_proposal_id"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_execution_intents_user_idempotency"
        ),
    )
    for column in ("created_at", "proposal_id", "state", "updated_at", "user_id"):
        op.create_index(f"ix_execution_intents_{column}", "execution_intents", [column])
