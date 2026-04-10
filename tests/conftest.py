from __future__ import annotations

import asyncio
import sys

import pytest
from collections.abc import AsyncGenerator
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.core.passwords import DEV_LOGIN_BCRYPT_HASH
from app.models.follow_up import FollowUp  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.user import User
from app.models.wallet_ledger import WalletLedgerEntry  # noqa: F401
from app.services.dev_users import DEV_EMAIL_BY_ROLE


async def _setup_sqlite() -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                User(
                    email=DEV_EMAIL_BY_ROLE["admin"],
                    role="admin",
                    hashed_password=DEV_LOGIN_BCRYPT_HASH,
                ),
                User(
                    email=DEV_EMAIL_BY_ROLE["leader"],
                    role="leader",
                    hashed_password=DEV_LOGIN_BCRYPT_HASH,
                ),
                User(
                    email=DEV_EMAIL_BY_ROLE["team"],
                    role="team",
                    hashed_password=DEV_LOGIN_BCRYPT_HASH,
                ),
            ]
        )
        await session.commit()
    return engine, factory


_engine, _session_factory = asyncio.run(_setup_sqlite())


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory() as session:
        yield session


from app.api.deps import get_db
from main import app

app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _disable_auth_rate_limit_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.config as cfg

    monkeypatch.setattr(
        cfg,
        "settings",
        cfg.settings.model_copy(update={"auth_login_rate_limit_per_minute": 0}),
    )


def get_test_session_factory() -> async_sessionmaker[AsyncSession]:
    """For tests that need to seed/query the same DB as the app override."""
    return _session_factory
