"""Seed 7-day training catalog when empty (legacy parity — day-by-day progress).

Revision ID: 20260413_0020
Revises: 20260412_0019
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260413_0020"
down_revision: Union[str, Sequence[str], None] = "20260412_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    n = conn.execute(sa.text("SELECT COUNT(*) FROM training_videos")).scalar()
    if int(n or 0) > 0:
        return
    rows = [
        (1, "Day 1 — Welcome & orientation"),
        (2, "Day 2 — Product basics"),
        (3, "Day 3 — Prospecting"),
        (4, "Day 4 — Follow-up"),
        (5, "Day 5 — Closing"),
        (6, "Day 6 — Leadership intro"),
        (7, "Day 7 — Certification prep"),
    ]
    for day_number, title in rows:
        conn.execute(
            sa.text(
                "INSERT INTO training_videos (day_number, title, youtube_url) "
                "VALUES (:d, :t, NULL)"
            ),
            {"d": day_number, "t": title},
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM training_videos WHERE day_number BETWEEN 1 AND 7"))
