"""Smoke tests for execution / other / settings stub routers."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


def _admin(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.api.deps as deps_mod
    import app.api.v1.auth as auth_mod
    from app.core.config import settings

    patched = settings.model_copy(
        update={
            "auth_dev_login_enabled": True,
            "secret_key": "unit-test-jwt-secret-at-least-32-chars!!",
        },
    )
    monkeypatch.setattr(auth_mod, "settings", patched)
    monkeypatch.setattr(deps_mod, "settings", patched)
    c = TestClient(app)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    return c


def test_execution_at_risk_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _admin(monkeypatch)
    r = c.get("/api/v1/execution/at-risk-leads")
    assert r.status_code == 200
    assert r.json()["note"]


def test_settings_app_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _admin(monkeypatch)
    assert c.get("/api/v1/settings/app").status_code == 200


def test_other_leaderboard_any_role(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.deps as deps_mod
    import app.api.v1.auth as auth_mod
    from app.core.config import settings

    patched = settings.model_copy(
        update={
            "auth_dev_login_enabled": True,
            "secret_key": "unit-test-jwt-secret-at-least-32-chars!!",
        },
    )
    monkeypatch.setattr(auth_mod, "settings", patched)
    monkeypatch.setattr(deps_mod, "settings", patched)
    c = TestClient(app)
    assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
    assert c.get("/api/v1/other/leaderboard").status_code == 200


def test_team_reports_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _admin(monkeypatch)
    assert c.get("/api/v1/team/reports").status_code == 200
