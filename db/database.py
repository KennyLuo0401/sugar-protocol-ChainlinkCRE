"""Async database connection management for Sugar Protocol."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import config
from db.models import Base

engine = create_async_engine(config.DB_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db(url: str | None = None) -> None:
    global engine, async_session_factory
    if url is not None:
        engine = create_async_engine(url, echo=False)
        async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class Database:
    """Thin wrapper for test compatibility."""

    def __init__(self, url: str | None = None):
        self._url = url

    async def init(self) -> None:
        await init_db(self._url)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with get_session() as s:
            yield s

    async def close(self) -> None:
        await engine.dispose()
