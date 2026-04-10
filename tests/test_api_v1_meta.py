import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_meta_public_shape() -> None:
    res = client.get("/api/v1/meta")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "myle-vl2"
    assert body["api_version"] == 1
    assert "environment" in body
    assert body["features"]["intelligence"] in (True, False)


def test_meta_intelligence_flag_respects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.v1.meta as meta_mod
    from app.core.config import settings as real_settings

    fake = real_settings.model_copy(
        update={
            "feature_intelligence": False,
            "app_environment": "test",
        },
    )
    monkeypatch.setattr(meta_mod, "settings", fake)
    res = client.get("/api/v1/meta")
    assert res.status_code == 200
    assert res.json()["features"]["intelligence"] is False
    assert res.json()["environment"] == "test"
