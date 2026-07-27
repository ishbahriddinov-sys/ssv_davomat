"""История посещений сотрудника."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.bot.handlers._helpers import TextKey
from app.core.enums import AttendanceStatus
from app.db.models import User
from app.i18n import t
from app.services import attendance_service

router = Router(name="history")


@router.message(TextKey("btn_history"))
async def show_history(message: Message, db_user: User | None, session):
    if not (db_user and db_user.is_verified):
        await message.answer(t("not_authorized"))
        return
    lang = db_user.language
    records = await attendance_service.get_history(session, db_user.id, days=30)

    if not records:
        await message.answer(t("history_empty", lang))
        return

    lines = [t("history_title", lang, n=30)]
    late = 0
    absent = 0
    for a in records:
        flags = ""
        if a.is_late:
            flags += "🟡"
            late += 1
        if a.status == AttendanceStatus.ABSENT:
            flags += "🔴"
            absent += 1
        lines.append(
            t("history_row", lang,
              date=a.work_date.isoformat(),
              in_=a.check_in.strftime("%H:%M") if a.check_in else "—",
              flags=flags)
        )
    lines.append(t("history_summary", lang, late=late, absent=absent))
    await message.answer("\n".join(lines))
