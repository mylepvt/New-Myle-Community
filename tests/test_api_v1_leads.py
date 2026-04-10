import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_list_leads_requires_auth() -> None:
    res = client.get("/api/v1/leads")
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
    assert res.json() == {"items": [], "total": 0}
    assert res.headers.get("X-Request-ID")
