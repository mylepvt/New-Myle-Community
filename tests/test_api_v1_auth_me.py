from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_auth_me_unauthenticated_shape() -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is False
    assert body.get("role") is None
    assert body.get("user_id") is None
    assert body.get("email") is None
