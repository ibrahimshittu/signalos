"""Store encrypted Expo devices, delivery tickets, and receipts.

Revision ID: 20260815_0007
Revises: 20260815_0006
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0007"
down_revision: str | None = "20260815_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_indexes(table: str, columns: Sequence[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("installation_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("expo_project_id", sa.String(36), nullable=False),
        sa.Column("token_ciphertext", sa.Text(), nullable=False),
        sa.Column("token_fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("last_registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("push_devices", ("expo_project_id", "status", "updated_at", "user_id"))

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("trade_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "installation_id",
            sa.String(36),
            sa.ForeignKey("push_devices.installation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expo_ticket_id", sa.String(100)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "proposal_id",
            "installation_id",
            "event_type",
            name="uq_notification_delivery_event",
        ),
    )
    _create_indexes(
        "notification_deliveries",
        (
            "created_at",
            "event_type",
            "expo_ticket_id",
            "installation_id",
            "proposal_id",
            "status",
            "updated_at",
            "user_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("push_devices")
