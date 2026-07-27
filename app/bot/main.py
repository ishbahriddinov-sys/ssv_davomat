"""Точка входа Telegram-бота (long polling)."""
from __future__ import annotations

import asyncio

from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.bot.handlers import register_handlers
from app.bot.loader import build_bot, build_dispatcher
from app.bot.middlewares.db import DBSessionMiddleware
from app.config import settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    bot = build_bot()
    dp = build_dispatcher()

    # Middleware БД для сообщений и callback-запросов
    dp.message.middleware(DBSessionMiddleware())
    dp.callback_query.middleware(DBSessionMiddleware())

    register_handlers(dp)

    me = await bot.get_me()
    logger.info("Бот запущен: @%s", me.username)

    # Кнопка меню для открытия Telegram Mini App (требуется HTTPS-адрес)
    if settings.webapp_url.startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Давомат", web_app=WebAppInfo(url=settings.webapp_url)
                )
            )
            logger.info("Кнопка меню Mini App установлена: %s", settings.webapp_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось установить кнопку Mini App: %s", exc)
    else:
        logger.info("WEBAPP_URL не задан (HTTPS) — кнопка Mini App пропущена.")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
