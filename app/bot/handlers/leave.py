"""Заявки на отпуск / больничный / командировку."""
from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers._helpers import TextKey
from app.bot.keyboards import inline, reply
from app.bot.states import LeaveStates
from app.core.enums import LeaveType
from app.db.models import User
from app.i18n import t
from app.services import hr_service, log_service

router = Router(name="leave")

_TYPE_MAP = {
    "vacation": LeaveType.VACATION,
    "sick": LeaveType.SICK,
    "trip": LeaveType.BUSINESS_TRIP,
    "unpaid": LeaveType.UNPAID,
}


@router.message(TextKey("btn_leave"))
async def leave_entry(message: Message, state: FSMContext, db_user: User | None):
    if not (db_user and db_user.is_verified):
        await message.answer(t("not_authorized"))
        return
    await message.answer(
        t("leave_choose_type", db_user.language),
        reply_markup=inline.leave_type_kb(db_user.language),
    )
    await state.set_state(LeaveStates.choosing_type)


@router.callback_query(LeaveStates.choosing_type, F.data.startswith("leave:"))
async def choose_type(call: CallbackQuery, state: FSMContext, db_user: User):
    key = call.data.split(":", 1)[1]
    await state.update_data(leave_type=key)
    await call.message.answer(t("leave_ask_start", db_user.language))
    await state.set_state(LeaveStates.waiting_start)
    await call.answer()


@router.message(LeaveStates.waiting_start, F.text)
async def ask_end(message: Message, state: FSMContext, db_user: User):
    lang = db_user.language
    try:
        date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer(t("leave_bad_date", lang))
        return
    await state.update_data(start=message.text.strip())
    await message.answer(t("leave_ask_end", lang))
    await state.set_state(LeaveStates.waiting_end)


@router.message(LeaveStates.waiting_end, F.text)
async def ask_reason(message: Message, state: FSMContext, db_user: User):
    lang = db_user.language
    try:
        date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer(t("leave_bad_date", lang))
        return
    await state.update_data(end=message.text.strip())
    await message.answer(t("leave_ask_reason", lang))
    await state.set_state(LeaveStates.waiting_reason)


@router.message(LeaveStates.waiting_reason, F.text)
async def submit_leave(
    message: Message, state: FSMContext, db_user: User, session: AsyncSession
):
    lang = db_user.language
    data = await state.get_data()
    leave = await hr_service.create_leave(
        session,
        user_id=db_user.id,
        leave_type=_TYPE_MAP.get(data["leave_type"], LeaveType.VACATION),
        start=date.fromisoformat(data["start"]),
        end=date.fromisoformat(data["end"]),
        reason=message.text.strip(),
    )
    await log_service.log_action(
        session, "leave.request", actor_id=db_user.id,
        actor_telegram_id=message.from_user.id, entity="leave", entity_id=leave.id,
    )
    await message.answer(t("leave_submitted", lang), reply_markup=reply.main_menu(db_user))
    await state.clear()
