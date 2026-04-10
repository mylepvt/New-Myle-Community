from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _authed(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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
    return TestClient(app)


def test_system_training_requires_auth() -> None:
    assert client.get("/api/v1/system/training").status_code == 401


def test_system_training_admin_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    r = c.get("/api/v1/system/training")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["note"]


def test_system_training_forbidden_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    assert c.get("/api/v1/system/training").status_code == 403


def test_system_decision_engine_admin_only(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    assert c.get("/api/v1/system/decision-engine").status_code == 403
    c2 = _authed(monkeypatch)
    assert c2.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    assert c2.get("/api/v1/system/decision-engine").status_code == 200


def test_system_coaching_admin_and_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
    assert c.get("/api/v1/system/coaching").status_code == 403

    c2 = _authed(monkeypatch)
    assert c2.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    assert c2.get("/api/v1/system/coaching").status_code == 200

    c3 = _authed(monkeypatch)
    assert c3.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    assert c3.get("/api/v1/system/coaching").status_code == 200
