from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import conftest as test_conftest
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.models.lead import Lead
from main import app

client = TestClient(app)


def test_list_leads_requires_auth() -> None:
    res = client.get("/api/v1/leads")
    assert res.status_code == 401


def test_lead_pool_requires_auth() -> None:
    res = client.get("/api/v1/lead-pool")
    assert res.status_code == 401
    assert res.headers.get("X-Request-ID")
    body = res.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"] == "Authentication required"
    assert body["error"]["request_id"] == res.headers.get("X-Request-ID")


def test_list_leads_empty_when_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    login = c.post("/api/v1/auth/dev-login", json={"role": "leader"})
    assert login.status_code == 200

    res = c.get("/api/v1/leads")
    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }
    assert res.headers.get("X-Request-ID")


async def _seed_one_lead(
    *,
    user_id: int,
    name: str = "Acme Corp",
    lead_status: str = "new",
    archived_at: datetime | None = None,
    deleted_at: datetime | None = None,
    in_pool: bool = False,
) -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        session.add(
            Lead(
                name=name,
                status=lead_status,
                created_by_user_id=user_id,
                archived_at=archived_at,
                deleted_at=deleted_at,
                in_pool=in_pool,
            )
        )
        await session.commit()


async def _clear_leads() -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        await session.execute(delete(Lead))
        await session.commit()


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


def test_list_leads_returns_db_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=2))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200

        res = c.get("/api/v1/leads")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "Acme Corp"
        assert body["items"][0]["status"] == "new"
        assert body["items"][0]["created_by_user_id"] == 2
        assert "id" in body["items"][0]
        assert "created_at" in body["items"][0]
    finally:
        asyncio.run(_clear_leads())


def test_leader_does_not_see_other_users_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=1, name="Admin lead"))
    asyncio.run(_seed_one_lead(user_id=2, name="Leader lead"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.get("/api/v1/leads")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Leader lead"
    finally:
        asyncio.run(_clear_leads())


def test_admin_sees_all_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=1, name="A"))
    asyncio.run(_seed_one_lead(user_id=2, name="B"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
        res = c.get("/api/v1/leads")
        assert res.status_code == 200
        assert res.json()["total"] == 2
    finally:
        asyncio.run(_clear_leads())


def test_create_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
        res = c.post("/api/v1/leads", json={"name": "  New Co  "})
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "New Co"
        assert body["status"] == "new"
        assert body["created_by_user_id"] == 3
        listed = c.get("/api/v1/leads").json()
        assert listed["total"] == 1
        assert listed["items"][0]["name"] == "New Co"
    finally:
        asyncio.run(_clear_leads())


def test_leader_cannot_patch_others_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=1, name="Owned by admin user"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.patch("/api/v1/leads/1", json={"name": "Hacked"})
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "forbidden"
    finally:
        asyncio.run(_clear_leads())


def test_delete_lead_returns_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=2, name="To delete"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.delete("/api/v1/leads/1")
        assert res.status_code == 204
        assert res.content == b""
        listed = c.get("/api/v1/leads").json()
        assert listed["total"] == 0
        again = c.delete("/api/v1/leads/1")
        assert again.status_code == 404
    finally:
        asyncio.run(_clear_leads())


def test_deleted_only_list_admin_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _seed_one_lead(
            user_id=2,
            name="Trashed",
            deleted_at=datetime.now(timezone.utc),
        )
    )
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        assert c.get("/api/v1/leads", params={"deleted_only": "true"}).status_code == 403

        c2 = _authed_client(monkeypatch)
        assert c2.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
        body = c2.get("/api/v1/leads", params={"deleted_only": "true"}).json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Trashed"
        assert body["items"][0]["deleted_at"] is not None
    finally:
        asyncio.run(_clear_leads())


def test_admin_restore_soft_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _seed_one_lead(
            user_id=2,
            name="Back",
            deleted_at=datetime.now(timezone.utc),
        )
    )
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
        rs = c.patch("/api/v1/leads/1", json={"restored": True})
        assert rs.status_code == 200
        assert rs.json()["deleted_at"] is None
        assert c.get("/api/v1/leads").json()["total"] == 1
    finally:
        asyncio.run(_clear_leads())


def test_admin_release_to_pool_hides_from_main_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=1, name="Pool me"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
        assert c.get("/api/v1/leads").json()["total"] == 1
        p = c.patch("/api/v1/leads/1", json={"in_pool": True})
        assert p.status_code == 200
        assert p.json()["in_pool"] is True
        assert c.get("/api/v1/leads").json()["total"] == 0
        pool = c.get("/api/v1/lead-pool").json()
        assert pool["total"] == 1
        assert pool["items"][0]["name"] == "Pool me"
    finally:
        asyncio.run(_clear_leads())


def test_claim_lead_from_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=1, name="Claimable", in_pool=True))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
        cl = c.post("/api/v1/leads/1/claim")
        assert cl.status_code == 200
        body = cl.json()
        assert body["in_pool"] is False
        assert body["created_by_user_id"] == 3
        assert c.get("/api/v1/lead-pool").json()["total"] == 0
        mine = c.get("/api/v1/leads").json()
        assert mine["total"] == 1
        assert mine["items"][0]["name"] == "Claimable"
    finally:
        asyncio.run(_clear_leads())


def test_archived_and_deleted_only_mutually_exclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    res = c.get(
        "/api/v1/leads",
        params={"archived_only": "true", "deleted_only": "true"},
    )
    assert res.status_code == 422


def test_list_leads_filter_by_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=2, name="A", lead_status="new"))
    asyncio.run(_seed_one_lead(user_id=2, name="B", lead_status="won"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.get("/api/v1/leads", params={"status": "won"})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "B"
        assert body["items"][0]["status"] == "won"
    finally:
        asyncio.run(_clear_leads())


def test_list_leads_search_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=2, name="Acme Industries"))
    asyncio.run(_seed_one_lead(user_id=2, name="Other LLC"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.get("/api/v1/leads", params={"q": "acme"})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Acme Industries"
    finally:
        asyncio.run(_clear_leads())


def test_list_leads_invalid_status_query_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    res = c.get("/api/v1/leads", params={"status": "nope"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "unprocessable_entity"


def test_patch_lead_status_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=2, name="X", lead_status="new"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.patch("/api/v1/leads/1", json={"status": "contacted"})
        assert res.status_code == 200
        assert res.json()["name"] == "X"
        assert res.json()["status"] == "contacted"
    finally:
        asyncio.run(_clear_leads())


def test_default_list_hides_archived_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _seed_one_lead(
            user_id=2,
            name="Gone",
            archived_at=datetime.now(timezone.utc),
        )
    )
    asyncio.run(_seed_one_lead(user_id=2, name="Here"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        body = c.get("/api/v1/leads").json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Here"
        assert body["items"][0]["archived_at"] is None
    finally:
        asyncio.run(_clear_leads())


def test_archived_only_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _seed_one_lead(
            user_id=2,
            name="Old",
            archived_at=datetime.now(timezone.utc),
        )
    )
    asyncio.run(_seed_one_lead(user_id=2, name="Active"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        body = c.get("/api/v1/leads", params={"archived_only": "true"}).json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Old"
        assert body["items"][0]["archived_at"] is not None
    finally:
        asyncio.run(_clear_leads())


def test_patch_archive_then_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_one_lead(user_id=2, name="Z"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        ar = c.patch("/api/v1/leads/1", json={"archived": True})
        assert ar.status_code == 200
        assert ar.json()["archived_at"] is not None
        assert c.get("/api/v1/leads").json()["total"] == 0
        rs = c.patch("/api/v1/leads/1", json={"archived": False})
        assert rs.status_code == 200
        assert rs.json()["archived_at"] is None
        assert c.get("/api/v1/leads").json()["total"] == 1
    finally:
        asyncio.run(_clear_leads())
