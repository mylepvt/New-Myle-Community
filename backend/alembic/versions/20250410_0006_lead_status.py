"""add leads.status

Revision ID: 20250410_0006
Revises: 20250410_0005
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250410_0006"
down_revision: Union[str, Sequence[str], None] = "20250410_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="new",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("leads", "status")
