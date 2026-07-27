"""HR-модуль в боте: сводка по опозданиям/прогулам/переработкам/отпускам."""
from __future__ import annotations

from datetime import timedelta

from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers._helpers import TextKey, has_role
from app.core.enums import Role
from app.db.models import User
from app.i18n import t
from app.services import attendance_service, hr_service

router = Router(name="hr")


@router.message(TextKey("btn_hr_panel"))
async def hr_panel(message: Message, db_user: User | None, session: AsyncSession):
    if not has_role(db_user, Role.HR, Role.ADMIN):
        await message.answer(t("access_denied"))
        return
    lang = db_user.language

    end = attendance_service.today_local()
    start = end - timedelta(days=30)
    summary = await hr_service.summary(session, start, end)

    text = t("hr_title", lang) + "\n\n" + t(
        "hr_summary", lang,
        period=f"{start} — {end}",
        late=summary.late_count,
        absent=summary.absent_count,
        overtime=summary.overtime_hours,
        on_leave=summary.on_leave_count,
        sick=summary.sick_count,
    )
    await message.answer(text)
