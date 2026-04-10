from fastapi.testclient import TestClient

import pytest

from app.core.passwords import DEV_LOGIN_PASSWORD_PLAIN
from main import app


def test_refresh_reissues_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.deps as deps_mod
    import app.api.v1.auth as auth_mod
    from app.core.config import settings

    patched = settings.model_copy(
        update={"secret_key": "unit-test-jwt-secret-at-least-32-chars!!"},
    )
    monkeypatch.setattr(auth_mod, "settings", patched)
    monkeypatch.setattr(deps_mod, "settings", patched)

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "dev-leader@myle.local", "password": DEV_LOGIN_PASSWORD_PLAIN},
    )
    assert login.status_code == 200
    assert "myle_access" in client.cookies
    assert "myle_refresh" in client.cookies

    ref = client.post("/api/v1/auth/refresh")
    assert ref.status_code == 200
    assert ref.json() == {"ok": True}

    me = client.get("/api/v1/auth/me")
    assert me.json()["authenticated"] is True
    assert me.json()["role"] == "leader"


def test_refresh_without_cookie_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v1.auth as auth_mod
    from app.core.config import settings

    patched = settings.model_copy(
        update={"secret_key": "unit-test-jwt-secret-at-least-32-chars!!"},
    )
    monkeypatch.setattr(auth_mod, "settings", patched)

    client = TestClient(app)
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"
