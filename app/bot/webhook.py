"""Запуск Telegram-бота в режиме webhook внутри FastAPI (один процесс).

Используется на Render/бесплатном хостинге, где нельзя держать отдельный
polling-процесс. Локально/на VPS бот по-прежнему может работать в polling
(app.bot.main) — режим переключается настройкой BOT_WEBHOOK_ENABLED.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.bot.handlers import register_handlers
from app.bot.loader import build_bot, build_dispatcher
from app.bot.middlewares.db import DBSessionMiddleware
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def webhook_path() -> str:
    return f"/telegram/webhook/{settings.webhook_token}"


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = build_bot()
    dp = build_dispatcher()
    dp.message.middleware(DBSessionMiddleware())
    dp.callback_query.middleware(DBSessionMiddleware())
    register_handlers(dp)
    return bot, dp


async def setup_webhook(bot: Bot, dp: Dispatcher) -> None:
    base = settings.base_url
    if not base:
        logger.warning("BASE_URL/RENDER_EXTERNAL_URL не задан — webhook не установлен.")
        return
    url = base + webhook_path()
    await bot.set_webhook(
        url,
        secret_token=settings.webhook_token,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )
    logger.info("Webhook установлен: %s", url)

    webapp = settings.effective_webapp_url
    if webapp.startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Давомат", web_app=WebAppInfo(url=webapp)
                )
            )
            logger.info("Кнопка меню Mini App установлена: %s", webapp)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Кнопка Mini App: %s", exc)


async def shutdown_webhook(bot: Bot) -> None:
    # ВАЖНО: webhook НЕ удаляем — на бесплатном хостинге сервис засыпает,
    # и удаление webhook оставило бы бота без обновлений. Webhook должен жить,
    # чтобы входящее сообщение «будило» сервис.
    try:
        await bot.session.close()
    except Exception:  # noqa: BLE001
        pass
