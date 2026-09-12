"""Persist reconciled broker orders, executions, and positions.

Revision ID: 20260815_0009
Revises: 20260815_0008
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0009"
down_revision: str | None = "20260815_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_indexes(table: str, columns: Sequence[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    for column in (
        sa.Column("category", sa.String(20)),
        sa.Column("symbol", sa.String(40)),
        sa.Column("side", sa.String(10)),
        sa.Column("order_type", sa.String(20)),
        sa.Column("quantity", sa.Numeric(30, 12)),
        sa.Column("cumulative_executed_quantity", sa.Numeric(30, 12)),
        sa.Column("leaves_quantity", sa.Numeric(30, 12)),
        sa.Column("average_price", sa.Numeric(30, 12)),
        sa.Column("broker_status", sa.String(40)),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("broker_orders", column)
    _create_indexes("broker_orders", ("last_reconciled_at", "symbol"))

    op.create_table(
        "broker_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "signalos_order_id",
            sa.String(36),
            sa.ForeignKey("broker_orders.id", ondelete="SET NULL"),
        ),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("broker_execution_id", sa.String(100), nullable=False),
        sa.Column("broker_order_id", sa.String(100), nullable=False),
        sa.Column("broker_order_link_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("price", sa.Numeric(30, 12), nullable=False),
        sa.Column("quantity", sa.Numeric(30, 12), nullable=False),
        sa.Column("value", sa.Numeric(30, 12), nullable=False),
        sa.Column("fee", sa.Numeric(30, 12), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id",
            "broker_execution_id",
            name="uq_broker_executions_connection_execution",
        ),
    )
    _create_indexes(
        "broker_executions",
        (
            "broker_order_id",
            "broker_order_link_id",
            "connection_id",
            "created_at",
            "environment",
            "executed_at",
            "signalos_order_id",
            "symbol",
            "user_id",
        ),
    )

    op.create_table(
        "broker_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("position_index", sa.Integer, nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("size", sa.Numeric(30, 12), nullable=False),
        sa.Column("average_price", sa.Numeric(30, 12), nullable=False),
        sa.Column("position_value", sa.Numeric(30, 12), nullable=False),
        sa.Column("leverage", sa.Numeric(12, 4), nullable=False),
        sa.Column("mark_price", sa.Numeric(30, 12), nullable=False),
        sa.Column("liquidation_price", sa.Numeric(30, 12)),
        sa.Column("take_profit", sa.Numeric(30, 12)),
        sa.Column("stop_loss", sa.Numeric(30, 12)),
        sa.Column("unrealised_pnl", sa.Numeric(30, 12), nullable=False),
        sa.Column("cumulative_realised_pnl", sa.Numeric(30, 12), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("broker_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id",
            "category",
            "symbol",
            "position_index",
            name="uq_broker_positions_account_instrument",
        ),
    )
    _create_indexes(
        "broker_positions",
        (
            "broker_updated_at",
            "closed_at",
            "connection_id",
            "environment",
            "last_reconciled_at",
            "opened_at",
            "state",
            "symbol",
            "user_id",
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "broker_executions" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "broker_positions" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("broker_positions")
    op.drop_table("broker_executions")
    op.drop_index("ix_broker_orders_symbol", table_name="broker_orders")
    op.drop_index("ix_broker_orders_last_reconciled_at", table_name="broker_orders")
    for column in (
        "last_reconciled_at",
        "broker_status",
        "average_price",
        "leaves_quantity",
        "cumulative_executed_quantity",
        "quantity",
        "order_type",
        "side",
        "symbol",
        "category",
    ):
        op.drop_column("broker_orders", column)
