"""API управления сотрудниками."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, require_role
from app.api.schemas import UserIn, UserOut
from app.core.enums import Role
from app.db.models import AdminUser, User
from app.db.session import get_db
from app.services import log_service, user_service

router = APIRouter(prefix="/api/users", tags=["users"])


def _to_out(user: User, *, include_phone: bool = True) -> UserOut:
    return UserOut(
        id=user.id,
        corporate_id=user.corporate_id,
        full_name=user_service.decrypt_name(user),
        # Телефон — ПДн: отдаём только полноправному администратору.
        phone=user_service.decrypt_phone(user) if include_phone else None,
        position=user.position,
        department_id=user.department_id,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@router.get("", response_model=list[UserOut])
async def list_users(
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    # Администраторы — системные учётки, в списке сотрудников не показываются
    res = await session.execute(
        select(User).where(User.role != Role.ADMIN).order_by(User.id)
    )
    include_phone = admin.role == Role.ADMIN
    return [_to_out(u, include_phone=include_phone) for u in res.scalars().all()]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserIn,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role(Role.ADMIN)),
):
    existing = await user_service.get_by_corporate_id(session, payload.corporate_id)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Корпоратив ID аллақачон мавжуд")
    user = await user_service.create_user(
        session,
        corporate_id=payload.corporate_id,
        full_name=payload.full_name,
        phone=payload.phone,
        position=payload.position,
        department_id=payload.department_id,
        role=payload.role,
    )
    await log_service.log_action(
        session, "api.user.create", entity="user", entity_id=user.id
    )
    await session.commit()
    return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserIn,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role(Role.ADMIN)),
):
    from app.core import security

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Топилмади")
    user.full_name_enc = security.encrypt(payload.full_name)
    if payload.phone is not None:
        user.phone_enc = security.encrypt(payload.phone)
    user.position = payload.position
    user.department_id = payload.department_id
    user.role = payload.role
    await log_service.log_action(
        session, "api.user.update", entity="user", entity_id=user.id
    )
    await session.commit()
    return _to_out(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role(Role.ADMIN)),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Топилмади")
    user.is_active = False  # мягкое удаление
    await log_service.log_action(
        session, "api.user.delete", entity="user", entity_id=user.id
    )
    await session.commit()
