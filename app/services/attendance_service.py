"""Основная бизнес-логика учёта посещаемости: приход, уход, расчёты."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import AttendanceStatus, CheckMethod
from app.db.models import Attendance, User

TZ = ZoneInfo(settings.timezone)


def now_local() -> datetime:
    return datetime.now(TZ)


def today_local() -> date:
    return now_local().date()


async def get_today(session: AsyncSession, user_id: int) -> Attendance | None:
    res = await session.execute(
        select(Attendance).where(
            Attendance.user_id == user_id, Attendance.work_date == today_local()
        )
    )
    return res.scalar_one_or_none()


def _combine(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=TZ)


async def check_in(
    session: AsyncSession,
    user: User,
    *,
    method: CheckMethod = CheckMethod.BUTTON,
    lat: float | None = None,
    lon: float | None = None,
    geo_verified: bool = False,
) -> tuple[Attendance, bool, int]:
    """Отметка прихода.

    Возвращает (attendance, is_new, late_minutes).
    """
    existing = await get_today(session, user.id)
    now = now_local()

    if existing and existing.check_in:
        return existing, False, existing.late_minutes

    work_start = _combine(now.date(), settings.work_start_time)
    late_minutes = 0
    is_late = False
    threshold = timedelta(minutes=settings.late_threshold_minutes)
    if now > work_start + threshold:
        late_minutes = int((now - work_start).total_seconds() // 60)
        is_late = True

    if existing:
        att = existing
    else:
        att = Attendance(user_id=user.id, work_date=now.date())
        session.add(att)

    att.check_in = now
    att.check_in_method = method
    att.check_in_lat = lat
    att.check_in_lon = lon
    att.geo_verified = geo_verified
    att.is_late = is_late
    att.late_minutes = late_minutes
    att.status = AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT
    await session.flush()
    return att, True, late_minutes


async def check_out(
    session: AsyncSession,
    user: User,
    *,
    method: CheckMethod = CheckMethod.BUTTON,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[Attendance | None, str]:
    """Отметка ухода и расчёт часов.

    Возвращает (attendance, status_code):
      status_code ∈ {"ok", "not_checked_in", "already"}.
    """
    att = await get_today(session, user.id)
    if not att or not att.check_in:
        return None, "not_checked_in"
    if att.check_out:
        return att, "already"

    now = now_local()
    att.check_out = now
    att.check_out_method = method
    att.check_out_lat = lat
    att.check_out_lon = lon

    check_in_dt = att.check_in
    if check_in_dt.tzinfo is None:
        check_in_dt = check_in_dt.replace(tzinfo=TZ)

    worked = int((now - check_in_dt).total_seconds() // 60)
    att.worked_minutes = max(worked, 0)

    standard = settings.standard_work_hours * 60
    att.overtime_minutes = max(worked - standard, 0)

    work_end = _combine(now.date(), settings.work_end_time)
    att.early_leave_minutes = max(int((work_end - now).total_seconds() // 60), 0)

    att.status = AttendanceStatus.COMPLETED
    await session.flush()
    return att, "ok"


async def get_history(
    session: AsyncSession, user_id: int, days: int = 30
) -> list[Attendance]:
    since = today_local() - timedelta(days=days)
    res = await session.execute(
        select(Attendance)
        .where(Attendance.user_id == user_id, Attendance.work_date >= since)
        .order_by(Attendance.work_date.desc())
    )
    return list(res.scalars().all())


async def get_range(
    session: AsyncSession, start: date, end: date, user_id: int | None = None
) -> list[Attendance]:
    stmt = select(Attendance).where(
        Attendance.work_date >= start, Attendance.work_date <= end
    )
    if user_id:
        stmt = stmt.where(Attendance.user_id == user_id)
    stmt = stmt.order_by(Attendance.work_date)
    res = await session.execute(stmt)
    return list(res.scalars().all())


def fmt_hours(minutes: int) -> str:
    h, m = divmod(max(minutes, 0), 60)
    return f"{h}:{m:02d}"
