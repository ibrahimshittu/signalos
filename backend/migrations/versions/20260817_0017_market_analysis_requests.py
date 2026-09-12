"""Add durable user-requested market analysis jobs.

Revision ID: 20260817_0017
Revises: 20260815_0016
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0017"
down_revision: str | None = "20260815_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_analysis_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=200), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_id", sa.String(length=36), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["scan_id"], ["market_scan_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "environment", "status", "requested_at"):
        op.create_index(
            f"ix_market_analysis_requests_{column}",
            "market_analysis_requests",
            [column],
        )
    op.create_index(
        "uq_market_analysis_requests_active_user_environment",
        "market_analysis_requests",
        ["user_id", "environment"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE market_analysis_requests ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(
        "uq_market_analysis_requests_active_user_environment",
        table_name="market_analysis_requests",
    )
    for column in reversed(("user_id", "environment", "status", "requested_at")):
        op.drop_index(
            f"ix_market_analysis_requests_{column}",
            table_name="market_analysis_requests",
        )
    op.drop_table("market_analysis_requests")
