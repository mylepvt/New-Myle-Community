"""Dev-only helpers for seeded accounts (see Alembic migration)."""

from __future__ import annotations

DEV_EMAIL_BY_ROLE = {
    "admin": "dev-admin@myle.local",
    "leader": "dev-leader@myle.local",
    "team": "dev-team@myle.local",
}


def dev_email_for_role(role: str) -> str:
    return DEV_EMAIL_BY_ROLE[role]
