"""Общие хендлеры: отмена, помощь, смена языка."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers._helpers import TextKey
from app.bot.keyboards import inline, reply
from app.config import settings
from app.db.models import User
from app.i18n import t
from app.services import user_service

router = Router(name="common")


@router.message(Command("app"))
async def open_app(message: Message, db_user: User | None):
    if not (db_user and db_user.is_verified):
        await message.answer(t("not_authorized"))
        return
    if not settings.webapp_url.startswith("https://"):
        await message.answer("ℹ️ Mini App ҳали созланмаган (HTTPS манзил керак).")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Иловани очиш",
                             web_app=WebAppInfo(url=settings.webapp_url))
    ]])
    await message.answer("📱 Давомат иловасини очинг:", reply_markup=kb)


@router.message(TextKey("cancel"))
async def cancel(message: Message, state: FSMContext, db_user: User | None):
    await state.clear()
    lang = db_user.language if db_user else None
    kb = reply.main_menu(db_user) if db_user else reply.remove
    await message.answer(t("cancelled", lang), reply_markup=kb)


@router.message(TextKey("btn_help"))
async def help_cmd(message: Message, db_user: User | None):
    lang = db_user.language if db_user else None
    await message.answer(t("help_text", lang))


@router.message(TextKey("btn_settings"))
async def settings_cmd(message: Message, db_user: User | None):
    lang = db_user.language if db_user else None
    await message.answer(t("choose_language", lang), reply_markup=inline.language_kb())


@router.callback_query(F.data.startswith("lang:"))
async def change_language(
    call: CallbackQuery, session: AsyncSession, db_user: User | None
):
    code = call.data.split(":", 1)[1]
    if db_user:
        await user_service.set_language(session, db_user, code)
        await call.message.answer(
            t("language_set", code), reply_markup=reply.main_menu(db_user)
        )
    else:
        # На этапе авторизации язык хранится в FSM (обрабатывается в auth)
        await call.message.answer(t("language_set", code))
    await call.answer()
