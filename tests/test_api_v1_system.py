from __future__ import annotations

import asyncio

import conftest as test_conftest
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.models.training_question import TrainingQuestion
from app.models.training_test_attempt import TrainingTestAttempt
from main import app

from util_jwt_patch import patch_jwt_settings

client = TestClient(app)


def _authed(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    patch_jwt_settings(monkeypatch, auth_dev_login_enabled=True)
    return TestClient(app)


def test_system_training_requires_auth() -> None:
    assert client.get("/api/v1/system/training").status_code == 401


def test_system_training_admin_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
    r = c.get("/api/v1/system/training")
    assert r.status_code == 200
    body = r.json()
    assert body["videos"] == []
    assert body["progress"] == []
    assert body.get("note")


def test_system_training_ok_for_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _authed(monkeypatch)
    assert c.post("/api/v1/auth/dev-login", json={"role": "leader"}).status_code == 200
    r = c.get("/api/v1/system/training")
    assert r.status_code == 200
    assert r.json()["videos"] == []
    assert r.json()["progress"] == []


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


async def _clear_training_tables() -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        await session.execute(delete(TrainingTestAttempt))
        await session.execute(delete(TrainingQuestion))
        await session.commit()


async def _seed_one_training_question() -> None:
    fac = test_conftest.get_test_session_factory()
    async with fac() as session:
        session.add(
            TrainingQuestion(
                question="Pick B",
                option_a="A",
                option_b="B",
                option_c="C",
                option_d="D",
                correct_answer="b",
                sort_order=1,
            )
        )
        await session.commit()


def test_training_test_questions_and_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_clear_training_tables())
    asyncio.run(_seed_one_training_question())
    try:
        c = _authed(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "team"}).status_code == 200
        qs = c.get("/api/v1/system/training-test/questions").json()
        assert len(qs) == 1
        assert "a" in qs[0]["options"]
        qid = qs[0]["id"]
        sub = c.post(
            "/api/v1/system/training-test/submit",
            json={"answers": {str(qid): "b"}},
        )
        assert sub.status_code == 200
        body = sub.json()
        assert body["score"] == 1
        assert body["passed"] is True
        assert body["percent"] == 100
        assert body.get("training_completed") is True
    finally:
        asyncio.run(_clear_training_tables())


def test_training_test_submit_errors_when_empty_bank(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_clear_training_tables())
    try:
        c = _authed(monkeypatch)
        assert c.post("/api/v1/auth/dev-login", json={"role": "admin"}).status_code == 200
        assert c.get("/api/v1/system/training-test/questions").json() == []
        r = c.post("/api/v1/system/training-test/submit", json={"answers": {}})
        assert r.status_code == 400
    finally:
        asyncio.run(_clear_training_tables())
