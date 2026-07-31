"""Веб-панель администратора: отдаёт HTML-страницы и обрабатывает вход по cookie."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import ratelimit, security
from app.db.models import AdminUser
from app.db.session import AsyncSessionLocal, get_db

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(tags=["admin-panel"])

PAGES = {
    "dashboard": "Асосий панель",
    "rollcall": "Йўқлама",
    "employees": "Ходимлар",
    "attendance": "Давомат",
    "departments": "Бўлимлар",
    "reports": "Ҳисоботлар",
    "logs": "Амаллар журнали",
    "settings": "Созламалар",
}

# Страницы, доступные не всем ролям панели
PAGE_ROLES = {
    "rollcall": {"hr", "admin"},   # перекличка — оператор (HR) и администратор
    "logs": {"admin"},             # журнал действий — только админ
}


def _visible_pages(role: str | None) -> dict[str, str]:
    return {
        key: label
        for key, label in PAGES.items()
        if role in PAGE_ROLES.get(key, {role})
    }


async def _current_admin(request: Request) -> AdminUser | None:
    """Проверяет JWT из cookie И актуальность учётной записи в БД (is_active)."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = security.decode_access_token(token)
    if not payload:
        return None
    async with AsyncSessionLocal() as session:
        admin = await session.get(AdminUser, int(payload["sub"]))
    if not admin or not admin.is_active:
        return None
    return admin


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if await _current_admin(request):
        return RedirectResponse("/admin/dashboard")
    return RedirectResponse("/admin/login")


@router.get("/admin")
async def admin_root(request: Request):
    if await _current_admin(request):
        return RedirectResponse("/admin/dashboard")
    return RedirectResponse("/admin/login")


@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/admin/login")
async def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(""),
    session: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else "?"
    ident = f"{ip}:{username}"

    blocked, retry = await ratelimit.is_blocked(ident)
    if blocked:
        return templates.TemplateResponse(
            "login.html",
            {"request": request,
             "error": f"Кириш уринишлари жуда кўп. {retry} сониядан сўнг қайта уриниб кўринг."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    res = await session.execute(
        select(AdminUser).where(AdminUser.username == username)
    )
    admin = res.scalar_one_or_none()
    error = None
    if not admin:
        security.dummy_verify()  # выравниваем тайминг ответа (анти-перечисление логинов)
    if not admin or not security.verify_password(password, admin.password_hash):
        error = "Логин ёки парол нотўғри"
    elif not admin.is_active:
        error = "Ҳисоб ўчирилган"
    elif admin.totp_enabled and not security.verify_totp(admin.totp_secret, totp_code):
        error = "Икки босқичли аутентификация коди нотўғри"

    if error:
        await ratelimit.register_failure(ident)
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": error},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    await ratelimit.clear(ident)
    token = security.create_access_token(admin.id, {"role": admin.role.value})
    resp = RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        "access_token", token, httponly=True, samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        secure=not settings.debug,
    )
    return resp


@router.get("/admin/logout")
async def logout():
    resp = RedirectResponse("/admin/login")
    resp.delete_cookie("access_token")
    return resp


@router.get("/admin/{page}", response_class=HTMLResponse)
async def admin_page(page: str, request: Request):
    if page not in PAGES:
        return RedirectResponse("/admin/dashboard")
    admin = await _current_admin(request)
    if not admin:
        return RedirectResponse("/admin/login")

    role = admin.role.value
    # Проверка доступа к странице по роли
    allowed = PAGE_ROLES.get(page)
    if allowed is not None and role not in allowed:
        return RedirectResponse("/admin/dashboard")

    return templates.TemplateResponse(
        f"{page}.html",
        {
            "request": request,
            "page": page,
            "pages": _visible_pages(role),
            "title": PAGES[page],
            "role": role,
        },
    )
