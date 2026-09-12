"""Fail closed for direct Supabase Data API access to backend-owned tables.

Revision ID: 20260815_0008
Revises: 20260815_0007
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_0008"
down_revision: str | None = "20260815_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKEND_TABLES = (
    "account_snapshots",
    "broker_connections",
    "broker_contexts",
    "broker_credentials",
    "broker_orders",
    "documents",
    "investment_profiles",
    "market_instruments",
    "market_latest_tickers",
    "market_scan_candidates",
    "market_scan_runs",
    "notification_deliveries",
    "order_reviews",
    "proposal_feedback",
    "push_devices",
    "run_events",
    "trade_proposals",
    "user_memories",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _BACKEND_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in _BACKEND_TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
