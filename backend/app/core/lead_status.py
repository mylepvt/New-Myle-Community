"""Allowed values for ``Lead.status`` (DB + API)."""

from __future__ import annotations

# Pipeline-friendly set; extend via migration + this tuple when product adds states.
LEAD_STATUS_SEQUENCE: tuple[str, ...] = (
    "new",
    "contacted",
    "qualified",
    "won",
    "lost",
)
LEAD_STATUS_SET: frozenset[str] = frozenset(LEAD_STATUS_SEQUENCE)
