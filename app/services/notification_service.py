"""Сервис уведомлений: сохранение и отправка через Telegram."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import NotificationType
from app.core.logging import get_logger
from app.db.models import Notification, User

logger = get_logger(__name__)


async def queue(
    session: AsyncSession,
    user_id: int,
    ntype: NotificationType,
    message: str,
) -> Notification:
    notif = Notification(user_id=user_id, ntype=ntype, message=message)
    session.add(notif)
    await session.flush()
    return notif


async def send_pending(session: AsyncSession, bot) -> int:
    """Отправляет все неотправленные уведомления. Возвращает число отправленных."""
    res = await session.execute(
        select(Notification, User)
        .join(User, Notification.user_id == User.id)
        .where(Notification.is_sent.is_(False), User.telegram_id.isnot(None))
    )
    sent = 0
    for notif, user in res.all():
        try:
            await bot.send_message(user.telegram_id, notif.message)
            notif.is_sent = True
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить уведомление %s: %s", notif.id, exc)
    await session.flush()
    return sent
