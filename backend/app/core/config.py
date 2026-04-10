from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Hosted Postgres often uses ``postgres://`` or ``postgresql://``; async engine needs ``+asyncpg``."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://myle:myle@localhost:5432/myle"
    )
    backend_cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    secret_key: str = Field(
        default="myle-vl2-dev-secret-change-with-SECRET_KEY-env",
        description="JWT signing + future session crypto",
    )
    auth_dev_login_enabled: bool = Field(
        default=False,
        validation_alias="AUTH_DEV_LOGIN_ENABLED",
    )
    session_cookie_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("SESSION_COOKIE_SECURE", "session_cookie_secure"),
    )
    auth_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        validation_alias=AliasChoices("AUTH_COOKIE_SAMESITE", "auth_cookie_samesite"),
        description="JWT cookie SameSite. Use ``none`` when the SPA and API are on different sites (requires Secure).",
    )
    jwt_access_minutes: int = Field(
        default=60,
        validation_alias="JWT_ACCESS_MINUTES",
        description="Access JWT lifetime (minutes).",
    )
    jwt_refresh_days: int = Field(
        default=14,
        validation_alias="JWT_REFRESH_DAYS",
        description="Refresh JWT lifetime (days).",
    )
    auth_login_rate_limit_per_minute: int = Field(
        default=30,
        validation_alias="AUTH_LOGIN_RATE_LIMIT_PER_MINUTE",
        description="Max POSTs per client IP per minute on auth login paths; 0 disables.",
    )
    app_environment: str = Field(
        default="development",
        validation_alias="APP_ENV",
        description="Label for clients (development | staging | production).",
    )
    feature_intelligence: bool = Field(
        default=True,
        validation_alias=AliasChoices("FEATURE_INTELLIGENCE", "FEATURE_AI_INTELLIGENCE"),
        description="Gates Work → Intelligence nav via GET /meta. No bundled third-party AI (e.g. Maya); product-only.",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def coerce_database_url(cls, v: object) -> object:
        if isinstance(v, str):
            return _normalize_database_url(v)
        return v

    @model_validator(mode="after")
    def none_samesite_requires_secure(self) -> "Settings":
        if self.auth_cookie_samesite == "none" and not self.session_cookie_secure:
            raise ValueError(
                "AUTH_COOKIE_SAMESITE=none requires SESSION_COOKIE_SECURE=true",
            )
        return self

    @property
    def database_url_sync(self) -> str:
        if "+asyncpg" in self.database_url:
            return self.database_url.replace("+asyncpg", "+psycopg2", 1)
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


settings = Settings()
