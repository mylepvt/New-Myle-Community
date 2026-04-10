"""add leads.deleted_at, leads.in_pool (pool + recycle bin)

Revision ID: 20250410_0009
Revises: 20250410_0008
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250410_0009"
down_revision: Union[str, Sequence[str], None] = "20250410_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "leads",
        sa.Column(
            "in_pool",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("leads", "in_pool")
    op.drop_column("leads", "deleted_at")
