"""Работа с пользователями и авторизацией."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.enums import Role
from app.db.models import Department, User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()


async def get_by_corporate_id(session: AsyncSession, corporate_id: str) -> User | None:
    res = await session.execute(
        select(User).where(User.corporate_id == corporate_id.strip())
    )
    return res.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


def decrypt_name(user: User) -> str:
    return security.decrypt(user.full_name_enc) or user.corporate_id


def decrypt_phone(user: User) -> str | None:
    return security.decrypt(user.phone_enc)


async def create_user(
    session: AsyncSession,
    *,
    corporate_id: str,
    full_name: str,
    phone: str | None = None,
    position: str | None = None,
    department_id: int | None = None,
    role: Role = Role.EMPLOYEE,
    telegram_id: int | None = None,
) -> User:
    user = User(
        corporate_id=corporate_id.strip(),
        full_name_enc=security.encrypt(full_name),
        phone_enc=security.encrypt(phone) if phone else None,
        position=position,
        department_id=department_id,
        role=role,
        telegram_id=telegram_id,
    )
    session.add(user)
    await session.flush()
    return user


async def bind_telegram(
    session: AsyncSession, user: User, telegram_id: int, language: str | None = None
) -> None:
    user.telegram_id = telegram_id
    user.is_verified = True
    if language:
        user.language = language
    await session.flush()


async def set_language(session: AsyncSession, user: User, language: str) -> None:
    user.language = language
    await session.flush()


async def verify_phone(user: User, phone: str) -> bool:
    """Сравнивает присланный телефон с сохранённым (нормализуя цифры)."""
    stored = security.decrypt(user.phone_enc)
    if not stored:
        return True  # телефон не задан — пропускаем проверку
    return _digits(stored) == _digits(phone)


def _digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())[-9:]


async def count_users(session: AsyncSession) -> int:
    res = await session.execute(select(func.count(User.id)))
    return res.scalar_one()


async def list_department_users(
    session: AsyncSession, department_id: int
) -> list[User]:
    res = await session.execute(
        select(User).where(
            User.department_id == department_id, User.is_active.is_(True)
        )
    )
    return list(res.scalars().all())
