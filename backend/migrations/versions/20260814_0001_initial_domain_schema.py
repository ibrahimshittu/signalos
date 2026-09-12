"""Create the initial SignalOS domain schema.

Revision ID: 20260814_0001
Revises:
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_indexes(table: str, columns: Sequence[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("account_id", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    _create_indexes("documents", ("account_id", "created_at", "kind", "status", "updated_at"))

    op.create_table(
        "run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_events_run_sequence"),
    )
    _create_indexes("run_events", ("created_at", "run_id"))

    op.create_table(
        "investment_profiles",
        sa.Column("user_id", sa.String(200), primary_key=True),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("intended_capital", sa.Numeric(24, 8), nullable=False),
        sa.Column("time_horizon", sa.String(40), nullable=False),
        sa.Column("liquidity_need", sa.String(40), nullable=False),
        sa.Column("investing_experience", sa.String(40), nullable=False),
        sa.Column("trading_experience", sa.String(40), nullable=False),
        sa.Column("products_traded", sa.JSON(), nullable=False),
        sa.Column("decision_frequency", sa.String(40), nullable=False),
        sa.Column("drawdown_response", sa.String(40), nullable=False),
        sa.Column("holding_periods", sa.JSON(), nullable=False),
        sa.Column("explanation_detail", sa.String(40), nullable=False),
        sa.Column("notification_frequency", sa.String(40), nullable=False),
        sa.Column("disclosures_accepted", sa.Boolean(), nullable=False),
        sa.Column("disclosures_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("investment_profiles", ("created_at", "updated_at"))

    op.create_table(
        "user_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    _create_indexes(
        "user_memories",
        ("created_at", "expires_at", "key", "kind", "updated_at", "user_id"),
    )

    op.create_table(
        "broker_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("provider_id", sa.String(40), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("external_uid", sa.String(100)),
        sa.Column("parent_uid", sa.String(100)),
        sa.Column("permission_fingerprint", sa.String(64)),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes(
        "broker_connections",
        (
            "created_at",
            "environment",
            "external_uid",
            "provider_id",
            "status",
            "updated_at",
            "user_id",
        ),
    )

    op.create_table(
        "broker_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("api_secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("external_uid", sa.String(100)),
        sa.Column("permission_fingerprint", sa.String(64)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id", "purpose", name="uq_broker_credentials_connection_purpose"
        ),
    )
    _create_indexes("broker_credentials", ("connection_id",))

    op.create_table(
        "account_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_type", sa.String(40), nullable=False),
        sa.Column("total_equity", sa.Numeric(30, 12), nullable=False),
        sa.Column("available_balance", sa.Numeric(30, 12), nullable=False),
        sa.Column("balances", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("account_snapshots", ("captured_at", "connection_id"))

    op.create_table(
        "trade_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("broker_connections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("strategy_version", sa.String(30), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("proposal_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("market_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    _create_indexes(
        "trade_proposals",
        (
            "connection_id",
            "created_at",
            "environment",
            "expires_at",
            "status",
            "strategy_id",
            "symbol",
            "updated_at",
            "user_id",
        ),
    )

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
    _create_indexes("trade_approvals", ("user_id",))

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
    _create_indexes(
        "execution_intents", ("created_at", "proposal_id", "state", "updated_at", "user_id")
    )

    op.create_table(
        "proposal_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(36),
            sa.ForeignKey("trade_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_indexes("proposal_feedback", ("created_at", "proposal_id", "reason", "user_id"))


def downgrade() -> None:
    op.drop_table("proposal_feedback")
    op.drop_table("execution_intents")
    op.drop_table("trade_approvals")
    op.drop_table("trade_proposals")
    op.drop_table("account_snapshots")
    op.drop_table("broker_credentials")
    op.drop_table("broker_connections")
    op.drop_table("user_memories")
    op.drop_table("investment_profiles")
    op.drop_table("run_events")
    op.drop_table("documents")
