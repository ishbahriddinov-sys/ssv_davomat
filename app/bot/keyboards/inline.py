"""Inline-клавиатуры (язык, отчёты, отпуска)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.i18n import LANG_NAMES, t


def language_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, name in LANG_NAMES.items():
        b.button(text=name, callback_data=f"lang:{code}")
    b.adjust(1)
    return b.as_markup()


def report_format_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Excel", callback_data="report:xlsx")
    b.button(text="📄 PDF", callback_data="report:pdf")
    b.button(text="📃 CSV", callback_data="report:csv")
    b.adjust(3)
    return b.as_markup()


def report_period_kb(lang: str, fmt: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("report_daily", lang), callback_data=f"rperiod:{fmt}:daily")
    b.button(text=t("report_weekly", lang), callback_data=f"rperiod:{fmt}:weekly")
    b.button(text=t("report_monthly", lang), callback_data=f"rperiod:{fmt}:monthly")
    b.adjust(1)
    return b.as_markup()


def leave_type_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏖 Vacation / Отпуск", callback_data="leave:vacation")
    b.button(text="🤒 Sick / Больничный", callback_data="leave:sick")
    b.button(text="💼 Trip / Командировка", callback_data="leave:trip")
    b.button(text="🕓 Unpaid / За свой счёт", callback_data="leave:unpaid")
    b.adjust(1)
    return b.as_markup()
