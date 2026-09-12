"""Persist AI-generated, user-editable investment preferences.

Revision ID: 20260815_0015
Revises: 20260815_0014
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0015"
down_revision: str | None = "20260815_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personalized_investment_policies",
        sa.Column("user_id", sa.String(length=200), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("profile_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_personalized_investment_policies_profile_updated_at",
        "personalized_investment_policies",
        ["profile_updated_at"],
    )
    op.create_index(
        "ix_personalized_investment_policies_created_at",
        "personalized_investment_policies",
        ["created_at"],
    )
    op.create_index(
        "ix_personalized_investment_policies_updated_at",
        "personalized_investment_policies",
        ["updated_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE personalized_investment_policies ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(
        "ix_personalized_investment_policies_updated_at",
        table_name="personalized_investment_policies",
    )
    op.drop_index(
        "ix_personalized_investment_policies_created_at",
        table_name="personalized_investment_policies",
    )
    op.drop_index(
        "ix_personalized_investment_policies_profile_updated_at",
        table_name="personalized_investment_policies",
    )
    op.drop_table("personalized_investment_policies")
