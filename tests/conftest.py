from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.example import Example  # noqa: F401
from app.models.user import User
from app.services.dev_users import DEV_EMAIL_BY_ROLE


async def _setup_sqlite() -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                User(email=DEV_EMAIL_BY_ROLE["admin"], role="admin"),
                User(email=DEV_EMAIL_BY_ROLE["leader"], role="leader"),
                User(email=DEV_EMAIL_BY_ROLE["team"], role="team"),
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
