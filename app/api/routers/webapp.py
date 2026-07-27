"""API для Telegram Mini App. Аутентификация — через подписанный initData."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path, PurePath
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AttendanceStatus, Role
from app.core.telegram_auth import validate_init_data
from app.db.models import User
from app.db.session import get_db
from app.services import (
    attendance_service,
    dashboard_service,
    department_service,
    log_service,
    rollcall_service,
    user_service,
)

router = APIRouter(prefix="/api/webapp", tags=["webapp"])

_TPL = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[2] / "admin" / "templates")
)

MAX_PROOF_BYTES = 10 * 1024 * 1024
ALLOWED_MIME = {
    "application/pdf", "image/jpeg", "image/png", "image/heic",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def get_webapp_user(
    x_telegram_init_data: str = Header(default=""),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Проверяет initData из заголовка и возвращает пользователя из БД."""
    data = validate_init_data(x_telegram_init_data)
    if not data or not data.get("user"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram маълумоти нотўғри")
    tg_id = data["user"].get("id")
    user = await user_service.get_by_telegram_id(session, tg_id)
    if not user or not user.is_verified or not user.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Аввал ботда авторизациядан ўтинг (/start)",
        )
    return user


def _safe_filename(name: str | None) -> str:
    if not name:
        return ""
    base = PurePath(name).name
    return re.sub(r'[\r\n"\\/\x00-\x1f]', "_", base)[:120]


# ==================== Страница Mini App ====================
@router.get("/", response_class=HTMLResponse)
async def webapp_page(request: Request):
    return _TPL.TemplateResponse("webapp.html", {"request": request})


# ==================== Профиль ====================
@router.get("/me")
async def me(
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_db),
):
    dept = None
    if user.department_id:
        d = await department_service.get_by_id(session, user.department_id)
        dept = d.name if d else None
    return {
        "name": user_service.decrypt_name(user),
        "role": user.role.value,
        "position": user.position,
        "department": dept,
        "corporate_id": user.corporate_id,
    }


# ==================== История сотрудника ====================
@router.get("/history")
async def history(
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_db),
):
    records = await attendance_service.get_history(session, user.id, days=30)
    late = sum(1 for a in records if a.is_late)
    absent = sum(1 for a in records if a.status == AttendanceStatus.ABSENT)
    return {
        "late": late,
        "absent": absent,
        "rows": [
            {
                "date": a.work_date.isoformat(),
                "check_in": a.check_in.strftime("%H:%M") if a.check_in else None,
                "status": a.status.value,
                "is_late": a.is_late,
                "late_minutes": a.late_minutes,
            }
            for a in records
        ],
    }


# ==================== Статистика (админ) ====================
@router.get("/stats")
async def stats(
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_db),
):
    if user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ҳуқуқлар етарли эмас")
    return await dashboard_service.stats(session)


# ==================== Перекличка (оператор HR) ====================
def _require_operator(user: User) -> None:
    if user.role not in (Role.HR, Role.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Йўқламани оператор ёки администратор ўтказади")


@router.get("/rollcall")
async def rollcall_roster(
    work_date: date | None = Query(None),
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_db),
):
    _require_operator(user)
    work_date = work_date or attendance_service.today_local()
    rows = await rollcall_service.roster(session, work_date)
    return {
        "date": work_date.isoformat(),
        "total": len(rows),
        "present": sum(1 for r in rows if r.status == "present"),
        "absent": sum(1 for r in rows if r.status == "absent"),
        "not_marked": sum(1 for r in rows if r.status == "not_marked"),
        "rows": [
            {
                "user_id": r.user_id, "full_name": r.full_name,
                "position": r.position, "department": r.department,
                "status": r.status, "is_late": r.is_late,
                "absence_reason": r.absence_reason, "has_proof": r.has_proof,
                "attendance_id": r.attendance_id,
            }
            for r in rows
        ],
    }


@router.post("/rollcall/present")
async def rc_present(
    user_id: int = Form(...),
    work_date: date = Form(...),
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_db),
):
    _require_operator(user)
    att = await rollcall_service.mark_present(session, user_id, work_date)
    await log_service.log_action(
        session, "webapp.rollcall.present", actor_id=user.id,
        actor_telegram_id=user.telegram_id, entity="attendance", entity_id=att.id,
    )
    await session.commit()
    return {"ok": True, "is_late": att.is_late}


@router.post("/rollcall/absent")
async def rc_absent(
    user_id: int = Form(...),
    work_date: date = Form(...),
    reason: str = Form(""),
    file: UploadFile | None = File(None),
    user: User = Depends(get_webapp_user),
    session: AsyncSession = Depends(get_db),
):
    _require_operator(user)
    filename = mime = None
    content = None
    if file is not None:
        content = await file.read()
        if len(content) > MAX_PROOF_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Файл 10 МБ дан катта")
        if file.content_type and file.content_type not in ALLOWED_MIME:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Файл тури мос эмас")
        filename = file.filename
        mime = file.content_type or "application/octet-stream"

    att = await rollcall_service.mark_absent(
        session, user_id, work_date,
        reason=reason or None, filename=filename, mime=mime, content=content,
    )
    await log_service.log_action(
        session, "webapp.rollcall.absent", actor_id=user.id,
        actor_telegram_id=user.telegram_id, entity="attendance", entity_id=att.id,
    )
    await session.commit()
    return {"ok": True, "has_proof": bool(content)}
