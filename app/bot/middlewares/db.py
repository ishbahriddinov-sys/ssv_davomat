"""Middleware: инъекция сессии БД и текущего пользователя в хендлеры."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from app.db.session import AsyncSessionLocal
from app.services import user_service


class DBSessionMiddleware(BaseMiddleware):
    """Открывает сессию на время обработки апдейта и коммитит в конце."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            tg_user: TgUser | None = data.get("event_from_user")
            if tg_user:
                db_user = await user_service.get_by_telegram_id(session, tg_user.id)
                data["db_user"] = db_user
                data["lang"] = db_user.language if db_user else None
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
