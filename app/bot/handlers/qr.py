"""QR-отметка в боте ОТКЛЮЧЕНА.

Отметку посещаемости проводит только администратор и оператор переклички
через веб-панель. Обработчик остаётся для информирования пользователей
со старыми клавиатурами.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app.bot.handlers._helpers import TextKey
from app.db.models import User
from app.i18n import t

router = Router(name="qr")


@router.message(TextKey("btn_qr"))
async def qr_disabled(message: Message, db_user: User | None):
    lang = db_user.language if db_user else None
    await message.answer(t("self_mark_disabled", lang))
