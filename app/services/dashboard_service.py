"""Агрегированные метрики для дашборда."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AttendanceStatus
from app.db.models import Attendance, Department, Leave, User
from app.services import attendance_service, department_service, user_service


async def stats(session: AsyncSession) -> dict:
    today = attendance_service.today_local()
    total_users = await user_service.count_users(session)
    total_depts = await department_service.count(session)

    day = await attendance_service.get_range(session, today, today)
    present = sum(1 for a in day if a.check_in)
    late = sum(1 for a in day if a.is_late)

    on_leave_res = await session.execute(
        select(func.count(Leave.id)).where(
            Leave.start_date <= today, Leave.end_date >= today
        )
    )
    on_leave = on_leave_res.scalar_one()

    absent = max(total_users - present - on_leave, 0)
    avg_min = (sum(a.worked_minutes for a in day) / present) if present else 0
    rate = round(present / total_users * 100, 1) if total_users else 0.0

    return {
        "total_users": total_users,
        "total_departments": total_depts,
        "present_today": present,
        "late_today": late,
        "absent_today": absent,
        "on_leave_today": on_leave,
        "avg_work_hours": round(avg_min / 60, 1),
        "attendance_rate": rate,
    }


async def attendance_trend(session: AsyncSession, days: int = 30) -> dict:
    """Динамика присутствия за последние N дней."""
    end = attendance_service.today_local()
    start = end - timedelta(days=days - 1)
    records = await attendance_service.get_range(session, start, end)

    by_day: dict[date, int] = {}
    for a in records:
        if a.check_in:
            by_day[a.work_date] = by_day.get(a.work_date, 0) + 1

    labels, values = [], []
    cur = start
    while cur <= end:
        labels.append(cur.strftime("%d.%m"))
        values.append(by_day.get(cur, 0))
        cur += timedelta(days=1)
    return {"labels": labels, "values": values}


async def department_ranking(session: AsyncSession) -> dict:
    """Рейтинг отделов по посещаемости за сегодня."""
    today = attendance_service.today_local()
    depts = await department_service.list_all(session)
    labels, values = [], []
    for dept in depts:
        employees = await user_service.list_department_users(session, dept.id)
        if not employees:
            continue
        present = 0
        for emp in employees:
            att = await attendance_service.get_today(session, emp.id)
            if att and att.check_in:
                present += 1
        rate = round(present / len(employees) * 100, 1)
        labels.append(dept.name)
        values.append(rate)
    return {"labels": labels, "values": values}


async def late_distribution(session: AsyncSession, days: int = 30) -> dict:
    """Распределение опозданий по дням."""
    end = attendance_service.today_local()
    start = end - timedelta(days=days - 1)
    records = await attendance_service.get_range(session, start, end)
    by_day: dict[date, int] = {}
    for a in records:
        if a.is_late:
            by_day[a.work_date] = by_day.get(a.work_date, 0) + 1
    labels, values = [], []
    cur = start
    while cur <= end:
        labels.append(cur.strftime("%d.%m"))
        values.append(by_day.get(cur, 0))
        cur += timedelta(days=1)
    return {"labels": labels, "values": values}
