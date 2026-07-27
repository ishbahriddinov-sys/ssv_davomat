"""Проверка подлинности Telegram Mini App (initData) через HMAC-SHA256.

См. https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.config import settings


def validate_init_data(init_data: str, max_age: int = 86400) -> dict | None:
    """Проверяет подпись initData и возвращает разобранные данные или None.

    Возвращает {"user": {...}, "auth_date": int} при успешной проверке.
    """
    if not init_data or not settings.bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()
    computed = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    # Проверка свежести (защита от повторного использования старых данных)
    auth_date = int(pairs.get("auth_date", "0") or 0)
    if max_age and auth_date and (time.time() - auth_date) > max_age:
        return None

    user = None
    if "user" in pairs:
        try:
            user = json.loads(pairs["user"])
        except json.JSONDecodeError:
            user = None

    return {"user": user, "auth_date": auth_date}
