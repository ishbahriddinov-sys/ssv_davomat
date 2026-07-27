"""Инициализация БД: создание таблиц и первичное наполнение (seed).

Идемпотентно — можно запускать многократно.
Запуск: python -m app.db.init_db
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.config import settings
from app.core import security
from app.core.enums import Role
from app.core.logging import get_logger, setup_logging
from app.db.base import Base
from app.db.models import AdminUser, Department, User
from app.db.session import AsyncSessionLocal, engine

logger = get_logger(__name__)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы созданы / актуальны.")


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # --- Администратор веб-панели по умолчанию ---
        res = await session.execute(
            select(AdminUser).where(AdminUser.username == "admin")
        )
        if not res.scalar_one_or_none():
            session.add(
                AdminUser(
                    username="admin",
                    password_hash=security.hash_password("admin123"),
                    full_name="Системный администратор",
                    role=Role.ADMIN,
                )
            )
            logger.info("Создан администратор панели: admin / admin123 (СМЕНИТЕ ПАРОЛЬ!)")

        # --- Демонстрационный отдел ---
        res = await session.execute(select(Department).limit(1))
        dept = res.scalar_one_or_none()
        if not dept:
            dept = Department(name="Аппарат Министерства", code="HQ")
            session.add(dept)
            await session.flush()
            logger.info("Создан демонстрационный отдел.")

        # --- Bootstrap-администраторы бота из .env ---
        for tg_id in settings.bootstrap_admin_ids:
            res = await session.execute(select(User).where(User.telegram_id == tg_id))
            if res.scalar_one_or_none():
                continue
            cid = f"ADMIN{tg_id}"
            res = await session.execute(select(User).where(User.corporate_id == cid))
            if res.scalar_one_or_none():
                continue
            session.add(
                User(
                    corporate_id=cid,
                    full_name_enc=security.encrypt("Администратор бота"),
                    telegram_id=tg_id,
                    role=Role.ADMIN,
                    department_id=dept.id,
                    is_verified=True,
                )
            )
            logger.info("Bootstrap-администратор бота: tg_id=%s", tg_id)

        await session.commit()


async def main() -> None:
    setup_logging()
    await create_tables()
    await seed()
    logger.info("Инициализация БД завершена.")


if __name__ == "__main__":
    asyncio.run(main())
