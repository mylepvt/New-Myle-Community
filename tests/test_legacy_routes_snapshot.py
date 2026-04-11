"""Ensure monolith ``routes/`` snapshot is complete under ``backend/legacy/``."""

from __future__ import annotations

from pathlib import Path

_EXPECTED = frozenset(
    {
        "__init__.py",
        "ai_routes.py",
        "approvals_routes.py",
        "auth_routes.py",
        "day2_eval_questions.py",
        "day2_test_routes.py",
        "enrollment_routes.py",
        "lead_pool_routes.py",
        "lead_routes.py",
        "misc_routes.py",
        "profile_routes.py",
        "progression_routes.py",
        "report_routes.py",
        "social_routes.py",
        "tasks_routes.py",
        "team_routes.py",
        "training_routes.py",
        "wallet_routes.py",
        "webhook_routes.py",
    }
)


def test_routes_snapshot_file_set() -> None:
    root = Path(__file__).resolve().parents[1] / "backend" / "legacy" / "myle_dashboard_main3" / "routes"
    names = {p.name for p in root.glob("*.py")}
    assert names == _EXPECTED, f"missing or extra: {_EXPECTED.symmetric_difference(names)}"
