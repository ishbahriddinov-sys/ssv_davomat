"""Демонстрационные данные: тестовые сотрудники, отделы и оператор переклички.

ВНИМАНИЕ: пересоздаёт схему (drop_all + create_all). Использовать только на
демо/тестовой базе — все существующие данные будут удалены.

Запуск: python -m app.db.seed_demo
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core import security
from app.core.enums import Role
from app.core.logging import get_logger, setup_logging
from app.db import init_db
from app.db.base import Base
from app.db.models import AdminUser, Department, User
from app.db.session import AsyncSessionLocal, engine

logger = get_logger(__name__)

DEPARTMENTS = [
    ("Аппарат Министерства", "HQ"),
    ("Управление лечебно-профилактической помощи", "LPP"),
    ("Отдел кадров", "HR"),
    ("Финансово-экономический отдел", "FIN"),
]

# (ФИО, должность, телефон, код отдела, роль)
EMPLOYEES = [
    ("Каримов Азиз Рустамович", "Начальник управления", "+998901112201", "LPP", Role.MANAGER),
    ("Юсупова Дилноза Шухратовна", "Главный специалист", "+998901112202", "LPP", Role.EMPLOYEE),
    ("Рахимов Бекзод Одилович", "Ведущий специалист", "+998901112203", "LPP", Role.EMPLOYEE),
    ("Ахмедова Нигора Фарходовна", "Специалист", "+998901112204", "LPP", Role.EMPLOYEE),
    ("Тошматов Жасур Улугбекович", "Специалист", "+998901112205", "LPP", Role.EMPLOYEE),
    ("Исмоилова Гулнора Азизовна", "Начальник отдела кадров", "+998901112206", "HR", Role.HR),
    ("Собиров Шерзод Каримович", "Инспектор по кадрам", "+998901112207", "HR", Role.EMPLOYEE),
    ("Абдуллаева Мадина Икромовна", "Специалист по кадрам", "+998901112208", "HR", Role.EMPLOYEE),
    ("Назаров Улугбек Тохирович", "Главный бухгалтер", "+998901112209", "FIN", Role.MANAGER),
    ("Хамидова Феруза Бахтиёровна", "Экономист", "+998901112210", "FIN", Role.EMPLOYEE),
    ("Эргашев Дониёр Санжарович", "Бухгалтер", "+998901112211", "FIN", Role.EMPLOYEE),
    ("Мирзаева Севара Алишеровна", "Референт министра", "+998901112212", "HQ", Role.EMPLOYEE),
    ("Холматов Фаррух Зафарович", "Помощник министра", "+998901112213", "HQ", Role.EMPLOYEE),
    ("Умарова Зарина Рустамовна", "Секретарь", "+998901112214", "HQ", Role.EMPLOYEE),
]


async def reset_schema() -> None:
    from sqlalchemy import text

    # Прямой сброс схемы: обходит циклическую зависимость FK users <-> departments
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Схема пересоздана (DROP SCHEMA public CASCADE + create_all).")


async def seed() -> None:
    await init_db.seed()  # admin панели + bootstrap-админы бота

    async with AsyncSessionLocal() as session:
        # --- Отделы ---
        code_to_dept: dict[str, Department] = {}
        for name, code in DEPARTMENTS:
            res = await session.execute(select(Department).where(Department.code == code))
            dept = res.scalar_one_or_none()
            if not dept:
                dept = Department(name=name, code=code)
                session.add(dept)
                await session.flush()
            code_to_dept[code] = dept

        # --- Сотрудники ---
        created = 0
        for idx, (full_name, position, phone, code, role) in enumerate(EMPLOYEES, start=1):
            corp = f"MOH{1000 + idx}"
            res = await session.execute(select(User).where(User.corporate_id == corp))
            if res.scalar_one_or_none():
                continue
            session.add(
                User(
                    corporate_id=corp,
                    full_name_enc=security.encrypt(full_name),
                    phone_enc=security.encrypt(phone),
                    position=position,
                    department_id=code_to_dept[code].id,
                    role=role,
                    is_active=True,
                )
            )
            created += 1

        await session.flush()

        # --- Назначаем руководителей отделов ---
        for code, mgr_corp in (("LPP", "MOH1001"), ("FIN", "MOH1009")):
            res = await session.execute(select(User).where(User.corporate_id == mgr_corp))
            mgr = res.scalar_one_or_none()
            if mgr:
                code_to_dept[code].manager_id = mgr.id

        # --- Оператор переклички (отдельный вход в панель) ---
        res = await session.execute(
            select(AdminUser).where(AdminUser.username == "rollcall")
        )
        if not res.scalar_one_or_none():
            session.add(
                AdminUser(
                    username="rollcall",
                    password_hash=security.hash_password("rollcall123"),
                    full_name="Оператор переклички (HR)",
                    role=Role.HR,
                )
            )
            logger.info("Создан вход оператора переклички: rollcall / rollcall123")

        await session.commit()
        logger.info("Добавлено тестовых сотрудников: %s", created)


def _guard_destructive() -> None:
    """Отказываемся выполнять DROP SCHEMA без явного подтверждения.

    Требуется переменная окружения ALLOW_DEMO_RESET=1 И выключенный production
    (DEBUG=true). Иначе случайный запуск против боевой БД сотрёт все данные.
    """
    import os

    from app.config import settings

    if os.getenv("ALLOW_DEMO_RESET") != "1":
        raise SystemExit(
            "ОТКАЗ: seed_demo пересоздаёт схему и удаляет ВСЕ данные. "
            "Запуск разрешён только с ALLOW_DEMO_RESET=1 на демо-базе."
        )
    if not settings.debug:
        raise SystemExit(
            "ОТКАЗ: DEBUG=false (похоже на production). Демо-сброс запрещён."
        )


async def main() -> None:
    setup_logging()
    _guard_destructive()
    await reset_schema()
    await seed()
    logger.info("Демо-данные готовы.")


if __name__ == "__main__":
    asyncio.run(main())
