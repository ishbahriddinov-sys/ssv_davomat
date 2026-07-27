"""Планировщик фоновых задач (APScheduler): напоминания и уведомления."""
from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.bot.loader import build_bot
from app.config import settings
from app.core.enums import NotificationType, Role
from app.core.logging import get_logger, setup_logging
from app.db.models import User
from app.db.session import get_session
from app.i18n import t
from app.services import attendance_service, notification_service

logger = get_logger(__name__)


async def remind_not_checked_in() -> None:
    """После начала рабочего дня напоминает не отметившимся."""
    async with get_session() as session:
        res = await session.execute(
            select(User).where(
                User.is_active.is_(True),
                User.is_verified.is_(True),
                User.telegram_id.isnot(None),
            )
        )
        for user in res.scalars().all():
            att = await attendance_service.get_today(session, user.id)
            if not att or not att.check_in:
                await notification_service.queue(
                    session, user.id, NotificationType.NOT_CHECKED_IN,
                    t("notif_not_checked_in", user.language),
                )


async def remind_checkout() -> None:
    """В конце рабочего дня напоминает отметить уход."""
    async with get_session() as session:
        res = await session.execute(
            select(User).where(
                User.is_active.is_(True), User.telegram_id.isnot(None)
            )
        )
        for user in res.scalars().all():
            att = await attendance_service.get_today(session, user.id)
            if att and att.check_in and not att.check_out:
                await notification_service.queue(
                    session, user.id, NotificationType.CHECKOUT_REMINDER,
                    t("notif_checkout_reminder", user.language),
                )


async def flush_notifications(bot) -> None:
    async with get_session() as session:
        sent = await notification_service.send_pending(session, bot)
        if sent:
            logger.info("Отправлено уведомлений: %s", sent)


async def main() -> None:
    setup_logging()
    bot = build_bot()
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    ws = settings.work_start_time
    we = settings.work_end_time

    # Напоминание неотметившимся — через 15 мин после начала дня (пн–пт)
    scheduler.add_job(
        remind_not_checked_in,
        CronTrigger(day_of_week="mon-fri", hour=ws.hour, minute=(ws.minute + 15) % 60),
    )
    # Напоминание об уходе — за 10 мин до конца дня
    scheduler.add_job(
        remind_checkout,
        CronTrigger(day_of_week="mon-fri", hour=we.hour, minute=max(we.minute - 10, 0)),
    )
    # Рассылка накопленных уведомлений — каждую минуту
    scheduler.add_job(flush_notifications, "interval", minutes=1, args=[bot])

    scheduler.start()
    logger.info("Планировщик запущен.")
    try:
        await asyncio.Event().wait()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
