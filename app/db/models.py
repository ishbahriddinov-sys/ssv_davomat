"""Модели базы данных.

Таблицы: Departments, Users, Attendance, QRSession, Leave,
Notification, ActionLog, AdminUser.
"""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AttendanceStatus,
    CheckMethod,
    LeaveStatus,
    LeaveType,
    NotificationType,
    Role,
)
from app.db.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), unique=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    # use_alter + именованный constraint — разрывает циклическую зависимость
    # users <-> departments при create_all / drop_all (DDL-уровень)
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL",
                   use_alter=True, name="fk_department_manager")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    manager: Mapped["User | None"] = relationship(
        "User", foreign_keys=[manager_id], post_update=True
    )
    employees: Mapped[list["User"]] = relationship(
        "User", back_populates="department", foreign_keys="User.department_id"
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)

    # Корпоративный идентификатор для авторизации
    corporate_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # ПДн (шифруются на уровне сервиса)
    full_name_enc: Mapped[str | None] = mapped_column(Text)
    phone_enc: Mapped[str | None] = mapped_column(Text)

    position: Mapped[str | None] = mapped_column(String(255))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, native_enum=False), default=Role.EMPLOYEE, nullable=False
    )
    language: Mapped[str] = mapped_column(String(2), default="ru")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # 2FA для администраторов
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    department: Mapped["Department | None"] = relationship(
        "Department", back_populates="employees", foreign_keys=[department_id]
    )
    attendances: Mapped[list["Attendance"]] = relationship(
        "Attendance", back_populates="user", cascade="all, delete-orphan"
    )


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("user_id", "work_date", name="uq_user_workday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    work_date: Mapped[date] = mapped_column(Date, index=True)

    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    check_in_method: Mapped[CheckMethod | None] = mapped_column(
        SAEnum(CheckMethod, native_enum=False)
    )
    check_out_method: Mapped[CheckMethod | None] = mapped_column(
        SAEnum(CheckMethod, native_enum=False)
    )

    # Геолокация
    check_in_lat: Mapped[float | None] = mapped_column(Float)
    check_in_lon: Mapped[float | None] = mapped_column(Float)
    check_out_lat: Mapped[float | None] = mapped_column(Float)
    check_out_lon: Mapped[float | None] = mapped_column(Float)
    geo_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, native_enum=False),
        default=AttendanceStatus.PRESENT,
    )

    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # ---- Перекличка (roll-call) ----
    marked_by_admin: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    absence_reason: Mapped[str | None] = mapped_column(Text)
    proof_filename: Mapped[str | None] = mapped_column(String(255))
    proof_mime: Mapped[str | None] = mapped_column(String(128))
    proof_content: Mapped[bytes | None] = mapped_column(LargeBinary)

    user: Mapped["User"] = relationship("User", back_populates="attendances")


class QRSession(Base, TimestampMixin):
    __tablename__ = "qr_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    valid_date: Mapped[date] = mapped_column(Date, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Тип: check_in / check_out
    purpose: Mapped[str] = mapped_column(String(16), default="check_in")


class Leave(Base, TimestampMixin):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    leave_type: Mapped[LeaveType] = mapped_column(SAEnum(LeaveType, native_enum=False))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeaveStatus] = mapped_column(
        SAEnum(LeaveStatus, native_enum=False), default=LeaveStatus.PENDING
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ntype: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, native_enum=False)
    )
    message: Mapped[str] = mapped_column(Text)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class ActionLog(Base, TimestampMixin):
    """Журнал всех действий (аудит)."""

    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))


class AdminUser(Base, TimestampMixin):
    """Учётные записи для веб-панели администратора."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, native_enum=False), default=Role.ADMIN
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
