"""Reply-клавиатуры (главное меню, запрос контакта/геолокации)."""
from __future__ import annotations

from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.core.enums import Role
from app.db.models import User
from app.i18n import t

remove = ReplyKeyboardRemove()


def main_menu(user: User) -> ReplyKeyboardMarkup:
    """Главное меню.

    Самостоятельная отметка прихода/ухода отключена: отметку проводит
    только администратор и оператор переклички через веб-панель.
    Рядовым сотрудникам доступны история и заявки на отпуск.
    """
    lang = user.language
    rows: list[list[KeyboardButton]] = []

    # Панели управления (только для соответствующих ролей)
    if user.role == Role.ADMIN:
        rows.append([
            KeyboardButton(text=t("btn_admin_panel", lang)),
            KeyboardButton(text=t("btn_hr_panel", lang)),
        ])
    elif user.role == Role.HR:
        rows.append([KeyboardButton(text=t("btn_hr_panel", lang))])
    elif user.role == Role.MANAGER:
        rows.append([KeyboardButton(text=t("btn_manager_panel", lang))])

    # Общее для всех
    rows.append([
        KeyboardButton(text=t("btn_history", lang)),
        KeyboardButton(text=t("btn_leave", lang)),
    ])
    rows.append([
        KeyboardButton(text=t("btn_settings", lang)),
        KeyboardButton(text=t("btn_help", lang)),
    ])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def request_phone(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("share_phone_btn", lang), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def request_location(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("share_geo_btn", lang), request_location=True)],
            [KeyboardButton(text=t("cancel", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
