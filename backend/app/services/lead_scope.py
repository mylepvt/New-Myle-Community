"""Reusable visibility rules for ``Lead`` rows (admin vs member scope)."""

from __future__ import annotations

from typing import Any, Optional

from app.api.deps import AuthUser
from app.models.lead import Lead


def lead_visibility_where(user: AuthUser) -> Optional[Any]:
    """None = no extra filter (admin sees all); else restrict to ``created_by_user_id``."""
    if user.role == "admin":
        return None
    return Lead.created_by_user_id == user.user_id
