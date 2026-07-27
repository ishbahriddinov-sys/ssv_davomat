"""Перекличка: ответственный отмечает присутствие/отсутствие сотрудников.

Для отсутствующих сохраняется причина и документ-доказательство.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import AttendanceStatus, CheckMethod
from app.db.models import Attendance, Department, User
from app.services import user_service

TZ = ZoneInfo(settings.timezone)


@dataclass
class RosterRow:
    user_id: int
    corporate_id: str
    full_name: str
    position: str | None
    department: str | None
    status: str          # present | absent | not_marked
    is_late: bool
    check_in: datetime | None
    absence_reason: str | None
    has_proof: bool
    attendance_id: int | None


async def _get_or_create(session: AsyncSession, user_id: int, work_date: date) -> Attendance:
    res = await session.execute(
        select(Attendance).where(
            Attendance.user_id == user_id, Attendance.work_date == work_date
        )
    )
    att = res.scalar_one_or_none()
    if not att:
        att = Attendance(user_id=user_id, work_date=work_date)
        session.add(att)
        await session.flush()
    return att


async def roster(
    session: AsyncSession, work_date: date, department_id: int | None = None
) -> list[RosterRow]:
    """Список активных сотрудников с их статусом на дату."""
    stmt = (
        select(User, Department)
        .join(Department, User.department_id == Department.id, isouter=True)
        .where(User.is_active.is_(True))
    )
    if department_id:
        stmt = stmt.where(User.department_id == department_id)
    stmt = stmt.order_by(Department.name, User.id)
    users = (await session.execute(stmt)).all()

    # Записи посещаемости на дату
    att_res = await session.execute(
        select(Attendance).where(Attendance.work_date == work_date)
    )
    att_map = {a.user_id: a for a in att_res.scalars().all()}

    rows: list[RosterRow] = []
    for user, dept in users:
        att = att_map.get(user.id)
        if att and att.status == AttendanceStatus.ABSENT:
            status = "absent"
        elif att and att.check_in:
            status = "present"
        else:
            status = "not_marked"
        rows.append(
            RosterRow(
                user_id=user.id,
                corporate_id=user.corporate_id,
                full_name=user_service.decrypt_name(user),
                position=user.position,
                department=dept.name if dept else None,
                status=status,
                is_late=bool(att and att.is_late),
                check_in=att.check_in if att else None,
                absence_reason=att.absence_reason if att else None,
                has_proof=bool(att and att.proof_content),
                attendance_id=att.id if att else None,
            )
        )
    return rows


async def mark_present(
    session: AsyncSession, user_id: int, work_date: date, admin_id: int | None = None
) -> Attendance:
    att = await _get_or_create(session, user_id, work_date)
    now = datetime.now(TZ)

    # Опоздание относительно начала рабочего дня (только для сегодняшней даты)
    is_late, late_min = False, 0
    if work_date == now.date():
        work_start = datetime.combine(work_date, settings.work_start_time, tzinfo=TZ)
        if now > work_start:
            late_min = int((now - work_start).total_seconds() // 60)
            is_late = late_min > settings.late_threshold_minutes
    check_in = datetime.combine(work_date, settings.work_start_time, tzinfo=TZ) \
        if work_date != now.date() else now

    att.check_in = check_in
    att.check_in_method = CheckMethod.MANUAL
    att.is_late = is_late
    att.late_minutes = late_min if is_late else 0
    att.status = AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT
    # сброс данных об отсутствии, если ранее был отмечен отсутствующим
    att.absence_reason = None
    att.proof_filename = None
    att.proof_mime = None
    att.proof_content = None
    att.marked_by_admin = admin_id
    await session.flush()
    return att


async def mark_absent(
    session: AsyncSession,
    user_id: int,
    work_date: date,
    *,
    reason: str | None = None,
    filename: str | None = None,
    mime: str | None = None,
    content: bytes | None = None,
    admin_id: int | None = None,
) -> Attendance:
    att = await _get_or_create(session, user_id, work_date)
    att.check_in = None
    att.check_out = None
    att.is_late = False
    att.late_minutes = 0
    att.worked_minutes = 0
    att.status = AttendanceStatus.ABSENT
    att.absence_reason = reason
    if content is not None:
        att.proof_filename = filename
        att.proof_mime = mime
        att.proof_content = content
    att.marked_by_admin = admin_id
    await session.flush()
    return att


async def get_proof(session: AsyncSession, attendance_id: int) -> Attendance | None:
    att = await session.get(Attendance, attendance_id)
    if not att or not att.proof_content:
        return None
    return att
