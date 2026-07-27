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
