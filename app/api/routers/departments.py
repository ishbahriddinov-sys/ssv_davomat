"""API управления подразделениями."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, require_role
from app.api.schemas import DepartmentIn, DepartmentOut
from app.core.enums import Role
from app.db.models import AdminUser, Department
from app.db.session import get_db
from app.services import department_service, log_service

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
async def list_departments(
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return await department_service.list_all(session)


@router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentIn,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role(Role.ADMIN)),
):
    dept = await department_service.create_department(
        session, payload.name, code=payload.code,
        parent_id=payload.parent_id, manager_id=payload.manager_id,
    )
    await log_service.log_action(
        session, "api.dept.create", entity="department", entity_id=dept.id
    )
    await session.commit()
    return dept


@router.patch("/{dept_id}", response_model=DepartmentOut)
async def update_department(
    dept_id: int,
    payload: DepartmentIn,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role(Role.ADMIN)),
):
    dept = await session.get(Department, dept_id)
    if not dept:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Топилмади")
    dept.name = payload.name
    dept.code = payload.code
    dept.parent_id = payload.parent_id
    dept.manager_id = payload.manager_id
    await log_service.log_action(
        session, "api.dept.update", entity="department", entity_id=dept.id
    )
    await session.commit()
    return dept
