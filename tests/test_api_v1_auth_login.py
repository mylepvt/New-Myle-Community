from fastapi.testclient import TestClient

import pytest

from app.core.passwords import DEV_LOGIN_PASSWORD_PLAIN
from main import app

client = TestClient(app)


def test_password_login_success(
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

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev-leader@myle.local", "password": DEV_LOGIN_PASSWORD_PLAIN},
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["authenticated"] is True
    assert body["role"] == "leader"


def test_password_login_wrong_password(
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

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev-leader@myle.local", "password": "wrong"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_password_login_unknown_email(
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

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": DEV_LOGIN_PASSWORD_PLAIN},
    )
    assert res.status_code == 401
