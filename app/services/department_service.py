"""Работа с подразделениями."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Department, User


async def create_department(
    session: AsyncSession,
    name: str,
    *,
    code: str | None = None,
    parent_id: int | None = None,
    manager_id: int | None = None,
) -> Department:
    dept = Department(name=name, code=code, parent_id=parent_id, manager_id=manager_id)
    session.add(dept)
    await session.flush()
    return dept


async def get_by_id(session: AsyncSession, dept_id: int) -> Department | None:
    return await session.get(Department, dept_id)


async def list_all(session: AsyncSession) -> list[Department]:
    res = await session.execute(select(Department).order_by(Department.name))
    return list(res.scalars().all())


async def count(session: AsyncSession) -> int:
    res = await session.execute(select(func.count(Department.id)))
    return res.scalar_one()


async def assign_manager(
    session: AsyncSession, dept: Department, manager_id: int
) -> None:
    dept.manager_id = manager_id
    await session.flush()


async def get_managed_department(
    session: AsyncSession, manager_user_id: int
) -> Department | None:
    res = await session.execute(
        select(Department).where(Department.manager_id == manager_user_id)
    )
    return res.scalars().first()
