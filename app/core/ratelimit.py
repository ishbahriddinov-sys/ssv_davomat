"""Защита от перебора пароля (login lockout).

Ключ = identifier (обычно "ip:username"). После N неудачных попыток в окне
доступ временно блокируется.

Хранилище выбирается автоматически:
  • REDIS_ENABLED=true  → Redis (общий для нескольких инстансов);
  • REDIS_ENABLED=false → надёжный in-memory счётчик в самом процессе
    (подходит для одно-инстансового хостинга: Render free, один VPS и т.п.).

Раньше при выключенном/недоступном Redis блокировка «падала» в fail-open и
защита от брутфорса фактически отключалась. Теперь всегда есть работающий
in-memory fallback — вход остаётся защищённым даже без Redis.
"""
from __future__ import annotations

import threading
import time

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis = None
_redis_broken = False  # если Redis сконфигурирован, но недоступен — переходим в память


# ==================== In-memory хранилище (fallback) ====================
class _MemoryStore:
    """Потокобезопасный счётчик неудачных попыток с TTL. Без внешних зависимостей."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}  # key -> (count, expires_at)
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        # Ленивая очистка протухших ключей, чтобы словарь не рос бесконечно.
        expired = [k for k, (_, exp) in self._data.items() if exp <= now]
        for k in expired:
            self._data.pop(k, None)

    def get(self, key: str) -> tuple[int, int]:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return 0, 0
            count, exp = item
            if exp <= now:
                self._data.pop(key, None)
                return 0, 0
            return count, int(exp - now)

    def incr(self, key: str, ttl: int) -> int:
        now = time.time()
        with self._lock:
            self._purge(now)
            item = self._data.get(key)
            if not item or item[1] <= now:
                self._data[key] = (1, now + ttl)
                return 1
            count = item[0] + 1
            self._data[key] = (count, item[1])  # TTL окна не продлеваем
            return count

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


_memory = _MemoryStore()


def _use_redis() -> bool:
    return bool(settings.redis_enabled) and not _redis_broken


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
    key = _key(identifier)
    if _use_redis():
        try:
            r = _client()
            val = await r.get(key)
            if val is not None and int(val) >= settings.login_max_attempts:
                ttl = await r.ttl(key)
                return True, max(ttl, 0)
            return False, 0
        except Exception as exc:  # noqa: BLE001
            _mark_redis_broken(exc)
    # In-memory
    count, ttl = _memory.get(key)
    if count >= settings.login_max_attempts:
        return True, ttl
    return False, 0


async def register_failure(identifier: str) -> None:
    """Фиксирует неудачную попытку входа."""
    key = _key(identifier)
    if _use_redis():
        try:
            r = _client()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, settings.login_lockout_seconds)
            return
        except Exception as exc:  # noqa: BLE001
            _mark_redis_broken(exc)
    _memory.incr(key, settings.login_lockout_seconds)


async def clear(identifier: str) -> None:
    """Сбрасывает счётчик после успешного входа."""
    key = _key(identifier)
    if _use_redis():
        try:
            await _client().delete(key)
            return
        except Exception as exc:  # noqa: BLE001
            _mark_redis_broken(exc)
    _memory.delete(key)


def _mark_redis_broken(exc: Exception) -> None:
    """Один раз логируем и навсегда переключаемся на in-memory (чтобы не спамить логи)."""
    global _redis_broken
    if not _redis_broken:
        logger.warning(
            "Redis недоступен для rate-limit — переключаюсь на in-memory блокировку: %s",
            exc,
        )
    _redis_broken = True
