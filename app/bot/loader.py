"""Инициализация бота, диспетчера и хранилища FSM (Redis)."""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.config import settings


def build_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_storage():
    if not settings.redis_enabled:
        return MemoryStorage()
    try:
        return RedisStorage.from_url(settings.redis_dsn)
    except Exception:
        return MemoryStorage()


def build_dispatcher() -> Dispatcher:
    return Dispatcher(storage=build_storage())
