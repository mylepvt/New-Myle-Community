import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_dev_login_disabled_returns_404(client: TestClient) -> None:
    res = client.post("/api/v1/auth/dev-login", json={"role": "admin"})
    assert res.status_code == 404
    assert res.headers.get("X-Request-ID")
    body = res.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == res.headers.get("X-Request-ID")


def test_dev_login_sets_cookie_and_me_matches(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v1.auth as auth_mod
    from app.core.config import settings

    monkeypatch.setattr(
        auth_mod,
        "settings",
        settings.model_copy(
            update={
                "auth_dev_login_enabled": True,
                "secret_key": "unit-test-jwt-secret-at-least-32-chars!!",
            },
        ),
    )

    res = client.post("/api/v1/auth/dev-login", json={"role": "leader"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["authenticated"] is True
    assert body["role"] == "leader"
    assert body["user_id"] == 2
    assert body["email"] == "dev-leader@myle.local"


def test_logout_clears_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v1.auth as auth_mod
    from app.core.config import settings

    monkeypatch.setattr(
        auth_mod,
        "settings",
        settings.model_copy(
            update={
                "auth_dev_login_enabled": True,
                "secret_key": "unit-test-jwt-secret-at-least-32-chars!!",
            },
        ),
    )

    client.post("/api/v1/auth/dev-login", json={"role": "team"})
    assert client.get("/api/v1/auth/me").json()["authenticated"] is True

    out = client.post("/api/v1/auth/logout")
    assert out.status_code == 200

    me = client.get("/api/v1/auth/me")
    body = me.json()
    assert body["authenticated"] is False
    assert body.get("role") is None
    assert body.get("user_id") is None
    assert body.get("email") is None
