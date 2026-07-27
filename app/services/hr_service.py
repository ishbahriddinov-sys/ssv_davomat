"""HR-модуль: агрегированные расчёты опозданий, прогулов, переработок, отпусков."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AttendanceStatus, LeaveStatus, LeaveType
from app.db.models import Attendance, Leave, User


@dataclass
class HRSummary:
    late_count: int
    absent_count: int
    overtime_hours: float
    on_leave_count: int
    sick_count: int


async def summary(
    session: AsyncSession,
    start: date,
    end: date,
    department_id: int | None = None,
) -> HRSummary:
    att_q = select(Attendance).join(User).where(
        Attendance.work_date >= start, Attendance.work_date <= end
    )
    if department_id:
        att_q = att_q.where(User.department_id == department_id)
    rows = (await session.execute(att_q)).scalars().all()

    late = sum(1 for a in rows if a.is_late)
    overtime_min = sum(a.overtime_minutes for a in rows)

    # Прогулы: активные сотрудники без записи в рабочий день (упрощённо — статус ABSENT)
    absent = sum(1 for a in rows if a.status == AttendanceStatus.ABSENT)

    leave_q = select(Leave).where(
        Leave.status == LeaveStatus.APPROVED,
        Leave.start_date <= end,
        Leave.end_date >= start,
    )
    if department_id:
        leave_q = leave_q.join(User).where(User.department_id == department_id)
    leaves = (await session.execute(leave_q)).scalars().all()

    on_leave = sum(1 for l in leaves if l.leave_type == LeaveType.VACATION)
    sick = sum(1 for l in leaves if l.leave_type == LeaveType.SICK)

    return HRSummary(
        late_count=late,
        absent_count=absent,
        overtime_hours=round(overtime_min / 60, 1),
        on_leave_count=on_leave,
        sick_count=sick,
    )


async def create_leave(
    session: AsyncSession,
    user_id: int,
    leave_type: LeaveType,
    start: date,
    end: date,
    reason: str | None = None,
) -> Leave:
    leave = Leave(
        user_id=user_id,
        leave_type=leave_type,
        start_date=start,
        end_date=end,
        reason=reason,
        status=LeaveStatus.PENDING,
    )
    session.add(leave)
    await session.flush()
    return leave


async def user_on_leave(session: AsyncSession, user_id: int, day: date) -> Leave | None:
    res = await session.execute(
        select(Leave).where(
            Leave.user_id == user_id,
            Leave.status == LeaveStatus.APPROVED,
            Leave.start_date <= day,
            Leave.end_date >= day,
        )
    )
    return res.scalars().first()
