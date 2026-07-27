"""Простая система интернационализации (uz / ru / en)."""
from __future__ import annotations

from app.i18n.locales import LOCALES

SUPPORTED = ("uz", "ru", "en")
DEFAULT = "uz"

LANG_NAMES = {"uz": "🇺🇿 Ўзбекча", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Возвращает переведённую строку по ключу с подстановкой параметров."""
    lang = lang if lang in SUPPORTED else DEFAULT
    table = LOCALES.get(lang, LOCALES[DEFAULT])
    text = table.get(key) or LOCALES[DEFAULT].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
