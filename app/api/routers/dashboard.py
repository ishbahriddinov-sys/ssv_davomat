"""API дашборда: статистика и данные для графиков."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.api.schemas import ChartSeries, DashboardStats
from app.db.models import AdminUser
from app.db.session import get_db
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return await dashboard_service.stats(session)


@router.get("/trend", response_model=ChartSeries)
async def get_trend(
    days: int = 30,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return await dashboard_service.attendance_trend(session, days)


@router.get("/ranking", response_model=ChartSeries)
async def get_ranking(
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return await dashboard_service.department_ranking(session)


@router.get("/late", response_model=ChartSeries)
async def get_late(
    days: int = 30,
    session: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return await dashboard_service.late_distribution(session, days)
