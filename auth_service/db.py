from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth_service.config import get_auth_settings

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        s = get_auth_settings()
        _engine = create_async_engine(s.DATABASE_URL, echo=False)
    return _engine


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    return _sessionmaker


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with _get_sessionmaker()() as session:
        yield session
