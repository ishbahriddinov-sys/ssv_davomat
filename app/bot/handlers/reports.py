"""Экспорт отчётов из бота (Excel / PDF / CSV)."""
from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers._helpers import at_least
from app.core.enums import Role
from app.db.models import User
from app.i18n import t
from app.services import attendance_service, log_service, report_service

router = Router(name="reports")


@router.callback_query(F.data.startswith("report:"))
async def choose_format(call: CallbackQuery, db_user: User | None):
    if not at_least(db_user, Role.MANAGER):
        await call.answer(t("access_denied"), show_alert=True)
        return
    from app.bot.keyboards import inline

    fmt = call.data.split(":", 1)[1]
    await call.message.answer(
        t("report_choose_period", db_user.language),
        reply_markup=inline.report_period_kb(db_user.language, fmt),
    )
    await call.answer()


@router.callback_query(F.data.startswith("rperiod:"))
async def generate(
    call: CallbackQuery, db_user: User | None, session: AsyncSession
):
    if not at_least(db_user, Role.MANAGER):
        await call.answer(t("access_denied"), show_alert=True)
        return
    lang = db_user.language
    _, fmt, period = call.data.split(":")

    end = attendance_service.today_local()
    if period == "daily":
        start = end
    elif period == "weekly":
        start = end - timedelta(days=7)
    else:
        start = end.replace(day=1)

    await call.message.answer(t("report_generating", lang))

    # HR/Admin — по всем; Руководитель — только по своему отделу
    dept_id = None
    if db_user.role == Role.MANAGER:
        dept_id = db_user.department_id

    if fmt == "xlsx":
        data = await report_service.to_excel(session, start, end, dept_id)
        fname, mime = f"report_{start}_{end}.xlsx", "xlsx"
    elif fmt == "pdf":
        data = await report_service.to_pdf(session, start, end, dept_id)
        fname, mime = f"report_{start}_{end}.pdf", "pdf"
    else:
        data = await report_service.to_csv(session, start, end, dept_id)
        fname, mime = f"report_{start}_{end}.csv", "csv"

    await log_service.log_action(
        session, "report.export", actor_id=db_user.id,
        actor_telegram_id=call.from_user.id, entity="report",
        details=f"{fmt}:{period}",
    )
    await call.message.answer_document(
        BufferedInputFile(data, filename=fname), caption=t("report_ready", lang)
    )
    await call.answer()
