"""API аутентификации администраторов панели (JWT + 2FA)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.api.schemas import Token
from app.core import ratelimit, security
from app.db.models import AdminUser
from app.db.session import get_db
from app.services import log_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else "?"
    ident = f"{ip}:{form.username}"

    blocked, retry = await ratelimit.is_blocked(ident)
    if blocked:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Слишком много попыток входа. Повторите через {retry} сек.",
        )

    res = await session.execute(
        select(AdminUser).where(AdminUser.username == form.username)
    )
    admin = res.scalar_one_or_none()
    if not admin or not security.verify_password(form.password, admin.password_hash):
        await ratelimit.register_failure(ident)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Логин ёки парол нотўғри")
    if not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ҳисоб ўчирилган")

    # Двухфакторная аутентификация для администраторов
    if admin.totp_enabled and admin.totp_secret:
        # OAuth2PasswordRequestForm использует поле scope для передачи кода
        code = (form.scopes[0] if form.scopes else "").strip()
        if not security.verify_totp(admin.totp_secret, code):
            await ratelimit.register_failure(ident)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "2FA коди талаб этилади")

    await ratelimit.clear(ident)
    admin.last_login = datetime.now(timezone.utc)
    await log_service.log_action(
        session, "admin.login", actor_id=None, entity="admin_user", entity_id=admin.id
    )
    await session.commit()

    token = security.create_access_token(admin.id, {"role": admin.role.value})
    return Token(access_token=token)


@router.get("/me")
async def me(admin: AdminUser = Depends(get_current_admin)):
    return {
        "id": admin.id,
        "username": admin.username,
        "full_name": admin.full_name,
        "role": admin.role.value,
        "totp_enabled": admin.totp_enabled,
    }
