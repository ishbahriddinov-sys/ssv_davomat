"""Отметка прихода/ухода в боте ОТКЛЮЧЕНА.

По решению: отметку проводит только администратор и оператор переклички
через веб-панель «Перекличка». Здесь остаётся лишь информирующий ответ
на случай устаревших клавиатур у пользователей.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.bot.handlers._helpers import TextKey
from app.db.models import User
from app.i18n import t

router = Router(name="attendance")


@router.message(TextKey("btn_check_in", "btn_check_out"))
async def marking_disabled(message: Message, db_user: User | None):
    lang = db_user.language if db_user else None
    await message.answer(t("self_mark_disabled", lang))
