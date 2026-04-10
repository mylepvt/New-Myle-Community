"""users table + dev seed rows

Revision ID: 20250410_0002
Revises: 20250410_0001
Create Date: 2026-04-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20250410_0002"
down_revision: Union[str, Sequence[str], None] = "20250410_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.execute(
        sa.text(
            "INSERT INTO users (email, role, hashed_password) VALUES "
            "('dev-admin@myle.local', 'admin', NULL), "
            "('dev-leader@myle.local', 'leader', NULL), "
            "('dev-team@myle.local', 'team', NULL)"
        )
    )


def downgrade() -> None:
    op.drop_table("users")
