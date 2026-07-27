"""API переклички: список сотрудников, отметка присутствия/отсутствия, док-во."""
from __future__ import annotations

import re
from datetime import date
from pathlib import PurePath
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_any_role
from app.core.enums import Role
from app.db.models import AdminUser
from app.db.session import get_db
from app.services import attendance_service, log_service, rollcall_service

router = APIRouter(prefix="/api/rollcall", tags=["rollcall"])

# Перекличку (отметку прихода) проводят оператор (роль HR) и администратор.
require_marker = require_any_role(Role.HR, Role.ADMIN)

MAX_PROOF_BYTES = 10 * 1024 * 1024  # 10 МБ
ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _safe_filename(name: str | None) -> str:
    """Безопасное имя файла: только базовое имя, без спецсимволов и переводов строк."""
    if not name:
        return ""
    base = PurePath(name).name  # убираем пути
    base = re.sub(r'[\r\n"\\/\x00-\x1f]', "_", base)  # убираем инъекции в заголовок
    return base[:120]


def _row_dict(r: rollcall_service.RosterRow) -> dict:
    return {
        "user_id": r.user_id,
        "corporate_id": r.corporate_id,
        "full_name": r.full_name,
        "position": r.position,
        "department": r.department,
        "status": r.status,
        "is_late": r.is_late,
        "check_in": r.check_in.isoformat() if r.check_in else None,
        "absence_reason": r.absence_reason,
        "has_proof": r.has_proof,
        "attendance_id": r.attendance_id,
    }


@router.get("")
async def get_roster(
    work_date: date | None = Query(None),
    department_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_marker),
):
    work_date = work_date or attendance_service.today_local()
    rows = await rollcall_service.roster(session, work_date, department_id)
    present = sum(1 for r in rows if r.status == "present")
    absent = sum(1 for r in rows if r.status == "absent")
    not_marked = sum(1 for r in rows if r.status == "not_marked")
    return {
        "date": work_date.isoformat(),
        "total": len(rows),
        "present": present,
        "absent": absent,
        "not_marked": not_marked,
        "rows": [_row_dict(r) for r in rows],
    }


@router.post("/present")
async def mark_present(
    user_id: int = Form(...),
    work_date: date = Form(...),
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_marker),
):
    att = await rollcall_service.mark_present(session, user_id, work_date, admin.id)
    await log_service.log_action(
        session, "rollcall.present", entity="attendance", entity_id=att.id,
        details=f"user={user_id} date={work_date} by_admin={admin.id}",
    )
    await session.commit()
    return {"ok": True, "status": "present", "is_late": att.is_late}


@router.post("/absent")
async def mark_absent(
    user_id: int = Form(...),
    work_date: date = Form(...),
    reason: str = Form(""),
    file: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_marker),
):
    filename = mime = None
    content = None
    if file is not None:
        content = await file.read()
        if len(content) > MAX_PROOF_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                "Файл 10 МБ дан катта")
        if file.content_type and file.content_type not in ALLOWED_MIME:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                "Файл тури мос эмас (PDF, JPG, PNG, DOC/DOCX)")
        filename = file.filename
        mime = file.content_type or "application/octet-stream"

    att = await rollcall_service.mark_absent(
        session, user_id, work_date,
        reason=reason or None, filename=filename, mime=mime, content=content,
        admin_id=admin.id,
    )
    await log_service.log_action(
        session, "rollcall.absent", entity="attendance", entity_id=att.id,
        details=f"user={user_id} date={work_date} proof={'yes' if content else 'no'}",
    )
    await session.commit()
    return {"ok": True, "status": "absent", "has_proof": bool(content)}


@router.get("/proof/{attendance_id}")
async def download_proof(
    attendance_id: int,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_marker),
):
    att = await rollcall_service.get_proof(session, attendance_id)
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ҳужжат топилмади")
    fname = _safe_filename(att.proof_filename) or f"proof_{attendance_id}"
    return Response(
        content=att.proof_content,
        media_type=att.proof_mime or "application/octet-stream",
        # attachment (не inline) + RFC 5987 filename* — исключаем инъекцию в заголовок
        # и запуск содержимого в браузере
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{fname}\"; "
                f"filename*=UTF-8''{quote(fname)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
