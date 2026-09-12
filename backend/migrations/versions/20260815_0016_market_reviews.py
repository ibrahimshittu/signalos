"""Persist explainable market-analysis outcomes.

Revision ID: 20260815_0016
Revises: 20260815_0015
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0016"
down_revision: str | None = "20260815_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_scan_runs",
        sa.Column("analysis_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "market_scan_runs", sa.Column("approved_strategy_count", sa.Integer(), nullable=True)
    )
    for name in (
        "candidates_considered",
        "strategy_matches",
        "signals_found",
        "analyses_completed",
        "no_trade_decisions",
        "proposals_created",
        "duplicates_skipped",
        "gate_rejections",
    ):
        op.add_column("market_scan_runs", sa.Column(name, sa.Integer(), nullable=True))
    op.add_column("market_scan_runs", sa.Column("model_available", sa.Boolean(), nullable=True))
    op.create_index(
        "ix_market_scan_runs_analysis_completed_at",
        "market_scan_runs",
        ["analysis_completed_at"],
    )
    op.add_column(
        "market_scan_candidates", sa.Column("review_status", sa.String(length=40), nullable=True)
    )
    op.add_column("market_scan_candidates", sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column(
        "market_scan_candidates",
        sa.Column("review_strategy_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_market_scan_candidates_review_status",
        "market_scan_candidates",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_scan_candidates_review_status", table_name="market_scan_candidates")
    op.drop_column("market_scan_candidates", "review_strategy_id")
    op.drop_column("market_scan_candidates", "review_reason")
    op.drop_column("market_scan_candidates", "review_status")
    op.drop_index("ix_market_scan_runs_analysis_completed_at", table_name="market_scan_runs")
    op.drop_column("market_scan_runs", "model_available")
    for name in reversed(
        (
            "candidates_considered",
            "strategy_matches",
            "signals_found",
            "analyses_completed",
            "no_trade_decisions",
            "proposals_created",
            "duplicates_skipped",
            "gate_rejections",
        )
    ):
        op.drop_column("market_scan_runs", name)
    op.drop_column("market_scan_runs", "approved_strategy_count")
    op.drop_column("market_scan_runs", "analysis_completed_at")
