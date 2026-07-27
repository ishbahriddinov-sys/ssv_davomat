"""Зависимости FastAPI: аутентификация администратора панели."""
from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.enums import ROLE_LEVEL, Role
from app.db.models import AdminUser
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def _resolve_admin(
    token: str | None, session: AsyncSession
) -> AdminUser:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Авторизациядан ўтилмаган")
    payload = security.decode_access_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нотўғри токен")
    admin = await session.get(AdminUser, int(payload["sub"]))
    if not admin or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Фойдаланувчи топилмади")
    return admin


async def get_current_admin(
    token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
) -> AdminUser:
    # Заголовок Authorization (API) или httponly-cookie (веб-панель)
    return await _resolve_admin(token or access_token, session)


async def get_admin_from_cookie(
    access_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Для веб-панели (кука)."""
    return await _resolve_admin(access_token, session)


def require_role(min_role: Role):
    async def checker(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if ROLE_LEVEL.get(admin.role, 0) < ROLE_LEVEL.get(min_role, 99):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Ҳуқуқлар етарли эмас")
        return admin

    return checker


def require_any_role(*roles: Role):
    """Доступ только для перечисленных ролей (без иерархии).

    Используется для переклички: только Администратор и Оператор (HR).
    """
    allowed = set(roles)

    async def checker(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Ҳуқуқлар етарли эмас")
        return admin

    return checker
