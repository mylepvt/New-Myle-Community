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


async def _seed_lead(
    *,
    user_id: int,
    name: str,
    lead_status: str,
    archived_at: datetime | None = None,
    in_pool: bool = False,
    deleted_at: datetime | None = None,
) -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        session.add(
            Lead(
                name=name,
                status=lead_status,
                created_by_user_id=user_id,
                archived_at=archived_at,
                in_pool=in_pool,
                deleted_at=deleted_at,
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


def test_workboard_requires_auth() -> None:
    res = client.get("/api/v1/workboard")
    assert res.status_code == 401


def test_workboard_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed_client(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    res = c.get("/api/v1/workboard")
    assert res.status_code == 200
    body = res.json()
    assert body["max_rows_fetched"] == 300
    assert len(body["columns"]) == 5
    for col in body["columns"]:
        assert col["total"] == 0
        assert col["items"] == []


def test_workboard_groups_and_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_lead(user_id=2, name="L1", lead_status="new"))
    asyncio.run(_seed_lead(user_id=2, name="L2", lead_status="won"))
    asyncio.run(_seed_lead(user_id=1, name="Admin only", lead_status="new"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.get("/api/v1/workboard")
        assert res.status_code == 200
        body = res.json()
        by_status = {c["status"]: c for c in body["columns"]}
        assert by_status["new"]["total"] == 1
        assert by_status["won"]["total"] == 1
        assert len(by_status["new"]["items"]) == 1
        assert by_status["new"]["items"][0]["name"] == "L1"

        c2 = _authed_client(monkeypatch)
        assert c2.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
        res2 = c2.get("/api/v1/workboard")
        by2 = {c["status"]: c for c in res2.json()["columns"]}
        assert by2["new"]["total"] == 2
    finally:
        asyncio.run(_clear_leads())


def test_workboard_excludes_pool_and_soft_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_lead(user_id=2, name="Pooled", lead_status="new", in_pool=True))
    asyncio.run(
        _seed_lead(
            user_id=2,
            name="Deleted",
            lead_status="new",
            deleted_at=datetime.now(timezone.utc),
        )
    )
    asyncio.run(_seed_lead(user_id=2, name="Active", lead_status="new"))
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.get("/api/v1/workboard")
        by_status = {col["status"]: col for col in res.json()["columns"]}
        assert by_status["new"]["total"] == 1
        assert len(by_status["new"]["items"]) == 1
        assert by_status["new"]["items"][0]["name"] == "Active"
    finally:
        asyncio.run(_clear_leads())


def test_workboard_excludes_archived_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_seed_lead(user_id=2, name="Active", lead_status="new"))
    asyncio.run(
        _seed_lead(
            user_id=2,
            name="Archived",
            lead_status="new",
            archived_at=datetime.now(timezone.utc),
        )
    )
    try:
        c = _authed_client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        res = c.get("/api/v1/workboard")
        by_status = {col["status"]: col for col in res.json()["columns"]}
        assert by_status["new"]["total"] == 1
        assert len(by_status["new"]["items"]) == 1
        assert by_status["new"]["items"][0]["name"] == "Active"
    finally:
        asyncio.run(_clear_leads())
