"""Hide Alembic bookkeeping from the Supabase Data API.

Revision ID: 20260815_0013
Revises: 20260815_0012
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_0013"
down_revision: str | None = "20260815_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "alembic_version" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "alembic_version" DISABLE ROW LEVEL SECURITY')
