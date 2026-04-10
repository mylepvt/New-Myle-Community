"""Settings helpers for hosted Postgres URLs and split-host cookie auth."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, _normalize_database_url


def test_normalize_database_url_asyncpg_unchanged() -> None:
    u = "postgresql+asyncpg://u:p@localhost:5432/db"
    assert _normalize_database_url(u) == u


def test_normalize_database_url_postgresql_prefix() -> None:
    u = "postgresql://u:p@db.example.com:5432/mydb"
    assert _normalize_database_url(u) == "postgresql+asyncpg://u:p@db.example.com:5432/mydb"


def test_normalize_database_url_postgres_prefix() -> None:
    u = "postgres://u:p@host:5432/db"
    assert _normalize_database_url(u) == "postgresql+asyncpg://u:p@host:5432/db"


def test_settings_coerces_database_url() -> None:
    s = Settings(
        database_url="postgresql://a:b@c:1/d",
        secret_key="x" * 40,
        backend_cors_origins="http://localhost:5173",
    )
    assert s.database_url == "postgresql+asyncpg://a:b@c:1/d"


def test_samesite_none_requires_secure() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+asyncpg://a:b@localhost/db",
            secret_key="x" * 40,
            backend_cors_origins="http://localhost:5173",
            auth_cookie_samesite="none",
            session_cookie_secure=False,
        )


def test_samesite_none_allowed_when_secure() -> None:
    s = Settings(
        database_url="postgresql+asyncpg://a:b@localhost/db",
        secret_key="x" * 40,
        backend_cors_origins="https://app.example.com",
        auth_cookie_samesite="none",
        session_cookie_secure=True,
    )
    assert s.auth_cookie_samesite == "none"
