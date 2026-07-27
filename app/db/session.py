"""Асинхронная сессия SQLAlchemy."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# Для внешней БД (Supabase): SSL обязателен; statement_cache_size=0 —
# совместимость с пулером pgbouncer (transaction mode).
_connect_args: dict = {}
if settings.is_external_db:
    _connect_args = {"ssl": True, "statement_cache_size": 0}

engine = create_async_engine(
    settings.sqlalchemy_dsn,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5 if settings.is_external_db else 10,
    max_overflow=10 if settings.is_external_db else 20,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Контекстный менеджер сессии (для бота, сервисов, планировщика)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
