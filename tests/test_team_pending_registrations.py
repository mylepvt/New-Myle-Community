"""Admin pending registration list + approve (legacy /admin/approvals parity)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.passwords import DEV_LOGIN_BCRYPT_HASH
from app.models.user import User
from conftest import get_test_session_factory
from main import app

from util_jwt_patch import patch_jwt_settings


def test_pending_registrations_list_and_approve(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_jwt_settings(monkeypatch, auth_dev_login_enabled=True)
    factory = get_test_session_factory()

    async def seed() -> int:
        async with factory() as session:
            u = User(
                fbo_id="pend01xx",
                username="penduser",
                email="pend01@test.local",
                role="team",
                registration_status="pending",
                hashed_password=DEV_LOGIN_BCRYPT_HASH,
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            return u.id

    uid = asyncio.run(seed())

    c = TestClient(app)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    r = c.get("/api/v1/team/pending-registrations")
    assert r.status_code == 200
    body = r.json()
    fbos = {x["fbo_id"] for x in body["items"]}
    assert "pend01xx" in fbos

    r2 = c.post(
        f"/api/v1/team/pending-registrations/{uid}/decision",
        json={"action": "approve"},
    )
    assert r2.status_code == 200
    assert r2.json()["registration_status"] == "approved"

    async def check() -> None:
        async with factory() as session:
            row = await session.get(User, uid)
            assert row is not None
            assert (row.registration_status or "").lower() == "approved"

    asyncio.run(check())
