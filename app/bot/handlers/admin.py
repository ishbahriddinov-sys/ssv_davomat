"""Панель администратора в боте: статистика, добавление сотрудников, отчёты, логи."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers._helpers import TextKey, has_role
from app.bot.keyboards import inline, reply
from app.bot.states import AdminStates
from app.core.enums import Role
from app.db.models import ActionLog, User
from app.i18n import t
from app.services import (
    attendance_service,
    department_service,
    log_service,
    user_service,
)

router = Router(name="admin")


@router.message(TextKey("btn_admin_panel"))
async def admin_panel(message: Message, db_user: User | None, session: AsyncSession):
    if not has_role(db_user, Role.ADMIN):
        await message.answer(t("access_denied"))
        return
    lang = db_user.language

    users = await user_service.count_users(session)
    depts = await department_service.count(session)
    today = attendance_service.today_local()
    day_records = await attendance_service.get_range(session, today, today)
    present = sum(1 for a in day_records if a.check_in)
    late = sum(1 for a in day_records if a.is_late)

    text = t("admin_title", lang) + "\n\n" + t(
        "admin_stats", lang, users=users, depts=depts, present=present, late=late
    )
    text += (
        f"\n\n{t('admin_add_user', lang)} — /add_user"
        f"\n{t('admin_logs', lang)} — /logs"
        f"\n{t('admin_export', lang)} — /export"
    )
    await message.answer(text)


@router.message(F.text == "/export")
async def export_cmd(message: Message, db_user: User | None):
    if not has_role(db_user, Role.ADMIN, Role.HR):
        await message.answer(t("access_denied"))
        return
    await message.answer(
        t("report_choose_format", db_user.language),
        reply_markup=inline.report_format_kb(db_user.language),
    )


@router.message(F.text == "/logs")
async def logs_cmd(message: Message, db_user: User | None, session: AsyncSession):
    if not has_role(db_user, Role.ADMIN):
        await message.answer(t("access_denied"))
        return
    res = await session.execute(
        select(ActionLog).order_by(desc(ActionLog.created_at)).limit(20)
    )
    logs = res.scalars().all()
    if not logs:
        await message.answer("📋 —")
        return
    lines = ["📋 <b>Журнал действий (20 последних):</b>"]
    for log in logs:
        lines.append(
            f"{log.created_at.strftime('%d.%m %H:%M')} · {log.action} · "
            f"tg:{log.actor_telegram_id or '—'}"
        )
    await message.answer("\n".join(lines))


# ---------- Добавление сотрудника (пошагово) ----------
@router.message(F.text == "/add_user")
async def add_user_start(message: Message, state: FSMContext, db_user: User | None):
    if not has_role(db_user, Role.ADMIN):
        await message.answer(t("access_denied"))
        return
    await message.answer("Введите корпоративный ID нового сотрудника:")
    await state.set_state(AdminStates.add_corporate_id)


@router.message(AdminStates.add_corporate_id, F.text)
async def add_user_name(message: Message, state: FSMContext):
    await state.update_data(corporate_id=message.text.strip())
    await message.answer("Введите ФИО:")
    await state.set_state(AdminStates.add_full_name)


@router.message(AdminStates.add_full_name, F.text)
async def add_user_phone(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("Введите номер телефона (или «-»):")
    await state.set_state(AdminStates.add_phone)


@router.message(AdminStates.add_phone, F.text)
async def add_user_position(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=None if phone == "-" else phone)
    await message.answer("Введите должность (или «-»):")
    await state.set_state(AdminStates.add_position)


@router.message(AdminStates.add_position, F.text)
async def add_user_finish(
    message: Message, state: FSMContext, db_user: User, session: AsyncSession
):
    data = await state.get_data()
    position = message.text.strip()
    existing = await user_service.get_by_corporate_id(session, data["corporate_id"])
    if existing:
        await message.answer("❌ Сотрудник с таким ID уже существует.",
                             reply_markup=reply.main_menu(db_user))
        await state.clear()
        return

    user = await user_service.create_user(
        session,
        corporate_id=data["corporate_id"],
        full_name=data["full_name"],
        phone=data.get("phone"),
        position=None if position == "-" else position,
    )
    await log_service.log_action(
        session, "admin.add_user", actor_id=db_user.id,
        actor_telegram_id=message.from_user.id, entity="user", entity_id=user.id,
    )
    await message.answer(
        f"✅ Сотрудник добавлен (ID: {user.corporate_id}).\n"
        f"Он сможет авторизоваться в боте по этому ID.",
        reply_markup=reply.main_menu(db_user),
    )
    await state.clear()
