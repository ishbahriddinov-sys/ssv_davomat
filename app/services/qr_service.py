"""Генерация и валидация QR-кодов для отметки посещаемости."""
from __future__ import annotations

import io
import secrets
from datetime import date, datetime, timedelta, timezone

import qrcode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import QRSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_qr_session(
    session: AsyncSession, purpose: str = "check_in"
) -> QRSession:
    """Создаёт новый QR-токен с ограниченным сроком жизни."""
    # деактивируем прошлые активные токены той же цели
    res = await session.execute(
        select(QRSession).where(
            QRSession.is_active.is_(True), QRSession.purpose == purpose
        )
    )
    for old in res.scalars().all():
        old.is_active = False

    token = secrets.token_urlsafe(24)
    qr = QRSession(
        token=token,
        valid_date=date.today(),
        expires_at=_now() + timedelta(seconds=settings.qr_ttl_seconds),
        is_active=True,
        purpose=purpose,
    )
    session.add(qr)
    await session.flush()
    return qr


async def validate_token(session: AsyncSession, token: str) -> QRSession | None:
    """Возвращает валидный QRSession или None (истёк/неактивен/нет)."""
    token = (token or "").strip()
    # Поддержка формата "moh:<token>"
    if token.startswith("moh:"):
        token = token[4:]
    res = await session.execute(select(QRSession).where(QRSession.token == token))
    qr = res.scalar_one_or_none()
    if not qr or not qr.is_active:
        return None
    expires = qr.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _now():
        return None
    return qr


def render_qr_png(token: str) -> bytes:
    """Генерирует PNG-изображение QR-кода."""
    payload = f"moh:{token}"
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
