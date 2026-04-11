from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _authed_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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


def test_team_members_requires_auth() -> None:
    res = client.get("/api/v1/team/members")
    assert res.status_code == 401


def test_team_members_admin_lists_users(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    res = c.get("/api/v1/team/members")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    emails = {x["email"] for x in body["items"]}
    assert "dev-admin@myle.local" in emails
    assert all("hashed_password" not in x for x in body["items"])
    assert all("password" not in str(x) for x in body["items"])


def test_team_members_forbidden_for_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    assert c.get("/api/v1/team/members").status_code == 403


def test_create_team_member_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    res = c.post(
        "/api/v1/team/members",
        json={
            "email": "new-member@myle.local",
            "password": "password123",
            "role": "team",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "new-member@myle.local"
    assert body["role"] == "team"
    assert "id" in body
    listed = c.get("/api/v1/team/members")
    emails = {x["email"] for x in listed.json()["items"]}
    assert "new-member@myle.local" in emails


def test_create_team_member_duplicate_email(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    payload = {"email": "dev-leader@myle.local", "password": "password123", "role": "team"}
    assert c.post("/api/v1/team/members", json=payload).status_code == 409


def test_create_team_member_forbidden_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    res = c.post(
        "/api/v1/team/members",
        json={"email": "x@myle.local", "password": "password123", "role": "team"},
    )
    assert res.status_code == 403


def test_create_team_member_short_password(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    res = c.post(
        "/api/v1/team/members",
        json={"email": "short-pw@myle.local", "password": "short", "role": "team"},
    )
    assert res.status_code == 422


def test_my_team_leader_returns_self(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    res = c.get("/api/v1/team/my-team")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["email"] == "dev-leader@myle.local"
    assert body["items"][0]["role"] == "leader"


def test_my_team_forbidden_for_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    assert c.get("/api/v1/team/my-team").status_code == 403


def test_enrollment_requests_empty_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    res = c.get("/api/v1/team/enrollment-requests")
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_enrollment_requests_empty_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    res = c.get("/api/v1/team/enrollment-requests")
    assert res.status_code == 200
    assert res.json()["total"] == 0


def test_enrollment_requests_forbidden_for_team(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
    assert c.get("/api/v1/team/enrollment-requests").status_code == 403
