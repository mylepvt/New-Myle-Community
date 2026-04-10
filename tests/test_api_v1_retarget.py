from __future__ import annotations

import asyncio

import conftest as test_conftest
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.models.lead import Lead
from main import app


async def _seed_lead(
    *,
    user_id: int,
    name: str,
    lead_status: str,
    in_pool: bool = False,
) -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        session.add(
            Lead(
                name=name,
                status=lead_status,
                created_by_user_id=user_id,
                in_pool=in_pool,
            )
        )
        await session.commit()


async def _clear() -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        await session.execute(delete(Lead))
        await session.commit()


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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


def test_retarget_requires_auth() -> None:
    assert TestClient(app).get("/api/v1/retarget").status_code == 401


def test_retarget_lists_lost_and_contacted_only(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_seed_lead(user_id=2, name="Cold", lead_status="lost"))
    asyncio.run(_seed_lead(user_id=2, name="Warm", lead_status="contacted"))
    asyncio.run(_seed_lead(user_id=2, name="Newbie", lead_status="new"))
    try:
        c = _client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        r = c.get("/api/v1/retarget")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        names = {x["name"] for x in data["items"]}
        assert names == {"Cold", "Warm"}
    finally:
        asyncio.run(_clear())


def test_retarget_excludes_pool_leads(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_seed_lead(user_id=2, name="Pooled lost", lead_status="lost", in_pool=True))
    asyncio.run(_seed_lead(user_id=2, name="Real lost", lead_status="lost"))
    try:
        c = _client(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
        data = c.get("/api/v1/retarget").json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Real lost"
    finally:
        asyncio.run(_clear())
