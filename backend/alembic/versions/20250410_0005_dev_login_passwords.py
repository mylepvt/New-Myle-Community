"""set dev bcrypt password for seeded users (dev/staging only)

Revision ID: 20250410_0005
Revises: 20250410_0004
Create Date: 2026-04-10

Plain password (documented in backend/.env.example): myle-dev-login
Hash generated with bcrypt 12 rounds — see app/core/passwords.py

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20250410_0005"
down_revision: Union[str, Sequence[str], None] = "20250410_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HASH = (
    "$2b$12$9Btds2bpJbyCRS7P2HUePeE6pJKr1DiIlPphCBt71eti7cNuViMjm"
)


def upgrade() -> None:
    op.execute(
        text(
            "UPDATE users SET hashed_password = :h WHERE email IN ("
            "'dev-admin@myle.local', 'dev-leader@myle.local', 'dev-team@myle.local')"
        ).bindparams(h=_HASH)
    )


def downgrade() -> None:
    op.execute(
        text(
            "UPDATE users SET hashed_password = NULL WHERE email IN ("
            "'dev-admin@myle.local', 'dev-leader@myle.local', 'dev-team@myle.local')"
        )
    )
