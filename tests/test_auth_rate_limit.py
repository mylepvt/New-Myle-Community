"""Rate limit middleware (must override autouse disable in conftest)."""

from fastapi.testclient import TestClient

import pytest

from app.middleware.auth_rate_limit import _reset_rate_limit_store_for_tests
from main import app


def test_auth_post_rate_limit_returns_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.config as cfg

    _reset_rate_limit_store_for_tests()
    monkeypatch.setattr(
        cfg,
        "settings",
        cfg.settings.model_copy(update={"auth_login_rate_limit_per_minute": 2}),
    )

    client = TestClient(app)
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "too_many_requests"
