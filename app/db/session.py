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
# совместимость с пулером (Supavisor/pgbouncer). Пулер Supabase отдаёт
# самоподписанный сертификат, поэтому режим require (шифруем, без проверки цепочки).
_connect_args: dict = {}
if settings.is_external_db:
    import ssl as _ssl

    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    _connect_args = {"ssl": _ctx, "statement_cache_size": 0}

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
