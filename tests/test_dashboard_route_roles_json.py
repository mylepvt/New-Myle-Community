"""Keep `frontend/src/config/dashboard-route-roles.json` aligned with product roles (no drift / typos)."""

from __future__ import annotations

import json
from pathlib import Path

from app.constants.roles import ROLES_SET

_ROOT = Path(__file__).resolve().parents[1]
_JSON = _ROOT / "frontend" / "src" / "config" / "dashboard-route-roles.json"


def test_dashboard_route_roles_json_exists_and_valid() -> None:
    assert _JSON.is_file(), f"Missing {_JSON}"
    data: dict[str, list[str]] = json.loads(_JSON.read_text(encoding="utf-8"))
    assert data, "frontend/src/config/dashboard-route-roles.json is empty"
    for path, roles in data.items():
        assert isinstance(path, str), path
        assert isinstance(roles, list) and len(roles) >= 1, path
        for r in roles:
            assert r in ROLES_SET, f"Invalid role {r!r} for path {path!r}"
