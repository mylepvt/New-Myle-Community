from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        validation_alias="SESSION_COOKIE_SECURE",
    )

    @property
    def database_url_sync(self) -> str:
        if "+asyncpg" in self.database_url:
            return self.database_url.replace("+asyncpg", "+psycopg2", 1)
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


settings = Settings()
