from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


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


def test_wallet_me_requires_auth() -> None:
    assert TestClient(app).get("/api/v1/wallet/me").status_code == 401


def test_wallet_me_zero_balance(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
    r = c.get("/api/v1/wallet/me")
    assert r.status_code == 200
    body = r.json()
    assert body["balance_cents"] == 0
    assert body["recent_entries"] == []


def test_wallet_adjustment_admin_then_balance(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    p = c.post(
        "/api/v1/wallet/adjustments",
        json={
            "user_id": 3,
            "amount_cents": 5000,
            "idempotency_key": "test-recharge-001",
            "note": "Test credit",
        },
    )
    assert p.status_code == 201
    assert p.json()["amount_cents"] == 5000

    c2 = _authed(monkeypatch)
    assert c2.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
    me = c2.get("/api/v1/wallet/me").json()
    assert me["balance_cents"] == 5000


def test_wallet_adjustment_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    body = {"user_id": 2, "amount_cents": 100, "idempotency_key": "idem-xyz-12345"}
    a = c.post("/api/v1/wallet/adjustments", json=body)
    b = c.post("/api/v1/wallet/adjustments", json=body)
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] == b.json()["id"]


def test_wallet_adjustment_forbidden_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    r = c.post(
        "/api/v1/wallet/adjustments",
        json={"user_id": 3, "amount_cents": 1, "idempotency_key": "nope-12345"},
    )
    assert r.status_code == 403


def test_wallet_ledger_admin_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    c.post(
        "/api/v1/wallet/adjustments",
        json={"user_id": 3, "amount_cents": 50, "idempotency_key": "ledger-a-unique-key"},
    )
    r = c.get("/api/v1/wallet/ledger", params={"user_id": 3})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
