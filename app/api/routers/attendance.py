"""API посещаемости."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.api.schemas import AttendanceOut
from app.db.models import AdminUser
from app.db.session import get_db
from app.services import attendance_service

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    start: date | None = Query(None),
    end: date | None = Query(None),
    user_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    end = end or attendance_service.today_local()
    start = start or (end - timedelta(days=30))
    return await attendance_service.get_range(session, start, end, user_id)
