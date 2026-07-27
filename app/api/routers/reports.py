"""API экспорта отчётов (Excel / PDF / CSV)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models import AdminUser
from app.db.session import get_db
from app.services import attendance_service, log_service, report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])

_MIME = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


@router.get("/export")
async def export(
    fmt: str = Query("xlsx", pattern="^(xlsx|csv|pdf)$"),
    start: date | None = None,
    end: date | None = None,
    department_id: int | None = None,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    end = end or attendance_service.today_local()
    start = start or end.replace(day=1)

    if fmt == "xlsx":
        data = await report_service.to_excel(session, start, end, department_id)
    elif fmt == "pdf":
        data = await report_service.to_pdf(session, start, end, department_id)
    else:
        data = await report_service.to_csv(session, start, end, department_id)

    await log_service.log_action(
        session, "api.report.export", entity="report", details=f"{fmt}:{start}:{end}"
    )
    await session.commit()

    filename = f"attendance_{start}_{end}.{fmt}"
    return Response(
        content=data,
        media_type=_MIME[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
