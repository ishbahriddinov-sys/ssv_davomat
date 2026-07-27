"""Панель руководителя: статус сотрудников отдела."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers._helpers import TextKey, at_least
from app.core.enums import Role
from app.db.models import User
from app.i18n import t
from app.services import (
    attendance_service,
    department_service,
    hr_service,
    user_service,
)

router = Router(name="manager")


@router.message(TextKey("btn_manager_panel"))
async def manager_panel(message: Message, db_user: User | None, session: AsyncSession):
    if not at_least(db_user, Role.MANAGER):
        await message.answer(t("access_denied"))
        return
    lang = db_user.language

    dept = await department_service.get_managed_department(session, db_user.id)
    if not dept and db_user.department_id:
        dept = await department_service.get_by_id(session, db_user.department_id)
    if not dept:
        await message.answer(t("mgr_no_dept", lang))
        return

    employees = await user_service.list_department_users(session, dept.id)
    today = attendance_service.today_local()

    present, absent, late, on_leave = [], [], [], []
    for emp in employees:
        att = await attendance_service.get_today(session, emp.id)
        leave = await hr_service.user_on_leave(session, emp.id, today)
        name = user_service.decrypt_name(emp)
        if leave:
            on_leave.append(name)
        elif att and att.check_in:
            if att.is_late:
                late.append(f"{name} (+{att.late_minutes}м)")
            else:
                present.append(name)
        else:
            absent.append(name)

    def block(title_key: str, items: list[str]) -> str:
        head = t(title_key, lang, n=len(items))
        body = "\n".join(f"  • {x}" for x in items) if items else "  —"
        return f"{head}\n{body}"

    text = "\n\n".join([
        t("mgr_title", lang, dept=dept.name),
        block("mgr_present", present),
        block("mgr_late", late),
        block("mgr_absent", absent),
        block("mgr_on_leave", on_leave),
        t("mgr_stats", lang, total=len(employees), present=len(present),
          late=len(late), absent=len(absent)),
    ])
    await message.answer(text)
