from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_migrations_shape() -> None:
    res = client.get("/health/migrations")
    assert res.status_code == 200
    body = res.json()
    assert "alembic_heads" in body
    assert isinstance(body["alembic_heads"], list)
    assert "current_revision" in body
    assert "at_head" in body


def test_security_headers_on_public_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
