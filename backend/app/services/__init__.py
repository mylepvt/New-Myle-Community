"""Domain / application services.

Monolith ``Myle-Dashboard-main-3/services/`` is mirrored under
``backend/legacy/myle_dashboard_main3/services/`` (verbatim). Runnable ports live here:

- ``rule_engine`` — aliases ``app.core.pipeline_rules``
- ``wallet_ledger`` — SQLite pool-spend helpers (legacy schema)
- ``day2_certificate_pdf`` — ReportLab Day 2 certificate PDF bytes
- ``scoring_service`` — points / progression (needs legacy ``point_history`` + optional ``database.get_db``)
- ``hierarchy_lead_sync`` — upline resolution + lead assignee sync (SQLite + ``daily_reports``)
"""

from __future__ import annotations

__all__ = [
    "day2_certificate_pdf",
    "hierarchy_lead_sync",
    "rule_engine",
    "scoring_service",
    "wallet_ledger",
]
