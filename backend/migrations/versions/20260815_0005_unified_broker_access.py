"""Use one verified broker credential for account access and explicit execution.

Revision ID: 20260815_0005
Revises: 20260815_0004
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0005"
down_revision: str | None = "20260815_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE broker_credentials SET purpose = 'broker_access' WHERE purpose = 'account_read'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE broker_credentials SET purpose = 'account_read' WHERE purpose = 'broker_access'"
        )
    )
