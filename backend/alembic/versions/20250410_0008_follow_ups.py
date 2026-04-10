"""follow_ups table

Revision ID: 20250410_0008
Revises: 20250410_0007
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250410_0008"
down_revision: Union[str, Sequence[str], None] = "20250410_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=2000), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_follow_ups_created_by_user_id_users"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], name="fk_follow_ups_lead_id_leads"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_follow_ups_lead_id", "follow_ups", ["lead_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_follow_ups_lead_id", table_name="follow_ups")
    op.drop_table("follow_ups")
