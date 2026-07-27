"""Вспомогательные функции и фильтры для хендлеров."""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.core.enums import ROLE_LEVEL, Role
from app.db.models import User
from app.i18n import SUPPORTED, t


class TextKey(BaseFilter):
    """Фильтр совпадения текста сообщения с i18n-ключом на любом языке."""

    def __init__(self, *keys: str) -> None:
        self.keys = keys

    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        variants = {
            t(key, lang) for key in self.keys for lang in SUPPORTED
        }
        return message.text in variants


def has_role(user: User | None, *roles: Role) -> bool:
    return bool(user and user.role in roles)


def at_least(user: User | None, role: Role) -> bool:
    if not user:
        return False
    return ROLE_LEVEL.get(user.role, 0) >= ROLE_LEVEL.get(role, 99)
