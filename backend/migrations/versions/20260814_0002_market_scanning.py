"""Add persisted market universe and deterministic scan snapshots.

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_indexes(table: str, columns: Sequence[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "market_instruments",
        sa.Column("environment", sa.String(20), primary_key=True),
        sa.Column("category", sa.String(20), primary_key=True),
        sa.Column("symbol", sa.String(40), primary_key=True),
        sa.Column("base_coin", sa.String(30), nullable=False),
        sa.Column("quote_coin", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("tick_size", sa.Numeric(30, 16), nullable=False),
        sa.Column("quantity_step", sa.Numeric(30, 16), nullable=False),
        sa.Column("minimum_order_quantity", sa.Numeric(30, 16), nullable=False),
        sa.Column("minimum_notional", sa.Numeric(30, 16), nullable=False),
        sa.Column("funding_interval_minutes", sa.Integer()),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("market_instruments", ("base_coin", "quote_coin", "refreshed_at", "status"))

    op.create_table(
        "market_latest_tickers",
        sa.Column("environment", sa.String(20), primary_key=True),
        sa.Column("category", sa.String(20), primary_key=True),
        sa.Column("symbol", sa.String(40), primary_key=True),
        sa.Column("last_price", sa.Numeric(30, 16), nullable=False),
        sa.Column("bid_price", sa.Numeric(30, 16), nullable=False),
        sa.Column("ask_price", sa.Numeric(30, 16), nullable=False),
        sa.Column("turnover_24h", sa.Numeric(38, 12), nullable=False),
        sa.Column("volume_24h", sa.Numeric(38, 12), nullable=False),
        sa.Column("price_change_24h", sa.Numeric(20, 12), nullable=False),
        sa.Column("open_interest", sa.Numeric(38, 12)),
        sa.Column("funding_rate", sa.Numeric(20, 12)),
        sa.Column("next_funding_at", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("market_latest_tickers", ("next_funding_at", "observed_at", "turnover_24h"))

    op.create_table(
        "market_scan_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("hot_count", sa.Integer(), nullable=False),
        sa.Column("shortlist_count", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("market_scan_runs", ("created_at", "environment", "observed_at"))

    op.create_table(
        "market_scan_candidates",
        sa.Column(
            "scan_id",
            sa.String(36),
            sa.ForeignKey("market_scan_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("category", sa.String(20), primary_key=True),
        sa.Column("symbol", sa.String(40), primary_key=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("selected_for_agent", sa.Boolean(), nullable=False),
        sa.Column("activity_score", sa.Numeric(20, 12), nullable=False),
        sa.Column("turnover_24h", sa.Numeric(38, 12), nullable=False),
        sa.Column("price_change_24h", sa.Numeric(20, 12), nullable=False),
        sa.Column("spread_bps", sa.Numeric(20, 12), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("market_scan_candidates", ("selected_for_agent",))


def downgrade() -> None:
    op.drop_table("market_scan_candidates")
    op.drop_table("market_scan_runs")
    op.drop_table("market_latest_tickers")
    op.drop_table("market_instruments")
