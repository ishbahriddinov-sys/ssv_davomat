"""Криптография: шифрование ПДн, JWT, 2FA (TOTP), хэш паролей."""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pyotp
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Фиктивный bcrypt-хэш для выравнивания времени ответа (защита от перечисления
# логинов по таймингу). Verify выполняется даже когда пользователь не найден.
_dummy_hash: str | None = None


def _get_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = pwd_context.hash("timing-equalizer")
    return _dummy_hash


def assert_secure_config() -> None:
    """В production (DEBUG=false) запрещаем работу с дефолтными секретами.

    С дефолтным JWT_SECRET любой может подделать токен администратора, поэтому
    небезопасный запуск лучше прервать явной ошибкой, чем «тихо» работать.
    """
    if settings.debug:
        return
    weak: list[str] = []
    if not settings.jwt_secret or settings.jwt_secret.strip().lower().startswith("change-me"):
        weak.append("JWT_SECRET")
    if not settings.secret_key or settings.secret_key.strip().lower().startswith("change-me"):
        weak.append("SECRET_KEY")
    if len(settings.jwt_secret or "") < 16:
        weak.append("JWT_SECRET (слишком короткий, нужно ≥16 символов)")
    if weak:
        raise RuntimeError(
            "Небезопасная конфигурация для production: задайте надёжные значения — "
            + ", ".join(weak)
            + ". Пример: openssl rand -hex 32"
        )


def dummy_verify() -> None:
    """Тратит примерно столько же времени, сколько verify_password, но всегда False."""
    try:
        pwd_context.verify("timing", _get_dummy_hash())
    except Exception:  # noqa: BLE001
        pass


# ==================== Шифрование ПДн (Fernet) ====================
def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # В production запрещаем работу без явного ключа шифрования ПДн.
        if not settings.debug:
            raise RuntimeError(
                "ENCRYPTION_KEY не задан. Сгенерируйте ключ Fernet и укажите его в .env "
                "(персональные данные не могут шифроваться слабым производным ключом)."
            )
        # Только для локальной разработки: детерминированный ключ из secret_key.
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str | None) -> str | None:
    """Шифрует строку персональных данных."""
    if value is None:
        return None
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str | None:
    """Дешифрует строку персональных данных."""
    if token is None:
        return None
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return token  # значение не было зашифровано (миграция)


# ==================== Пароли (admin panel) ====================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ==================== JWT (admin panel / API) ====================
def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ==================== 2FA (TOTP) для администраторов ====================
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name, issuer_name="MoH Attendance"
    )


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


# ==================== Одноразовые коды подтверждения ====================
def generate_otp(length: int = 6) -> str:
    import secrets

    return "".join(secrets.choice("0123456789") for _ in range(length))
