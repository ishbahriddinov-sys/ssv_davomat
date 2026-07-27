"""Защита от перебора пароля (login lockout) на базе Redis.

Ключ = identifier (обычно "ip:username"). После N неудачных попыток в окне
доступ временно блокируется. При недоступности Redis — fail-open
(вход не блокируется, чтобы не «положить» систему из-за кэша).
"""
from __future__ import annotations

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis = None


def _client():
    global _redis
    if _redis is None:
        from redis.asyncio import Redis

        _redis = Redis.from_url(settings.redis_dsn, decode_responses=True)
    return _redis


def _key(identifier: str) -> str:
    return f"login_fail:{identifier}"


async def is_blocked(identifier: str) -> tuple[bool, int]:
    """Возвращает (заблокировано?, осталось секунд)."""
    try:
        r = _client()
        val = await r.get(_key(identifier))
        if val is not None and int(val) >= settings.login_max_attempts:
            ttl = await r.ttl(_key(identifier))
            return True, max(ttl, 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis недоступен для rate-limit (fail-open): %s", exc)
    return False, 0


async def register_failure(identifier: str) -> None:
    """Фиксирует неудачную попытку входа."""
    try:
        r = _client()
        key = _key(identifier)
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, settings.login_lockout_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis недоступен для rate-limit (fail-open): %s", exc)


async def clear(identifier: str) -> None:
    """Сбрасывает счётчик после успешного входа."""
    try:
        await _client().delete(_key(identifier))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis недоступен для rate-limit (fail-open): %s", exc)
