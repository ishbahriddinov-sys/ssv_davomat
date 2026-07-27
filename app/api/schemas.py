"""Pydantic-схемы REST API."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import AttendanceStatus, Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class DepartmentIn(BaseModel):
    name: str
    code: str | None = None
    parent_id: int | None = None
    manager_id: int | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str | None
    manager_id: int | None
    is_active: bool


class UserIn(BaseModel):
    corporate_id: str
    full_name: str
    phone: str | None = None
    position: str | None = None
    department_id: int | None = None
    role: Role = Role.EMPLOYEE


class UserOut(BaseModel):
    id: int
    corporate_id: str
    full_name: str
    phone: str | None
    position: str | None
    department_id: int | None
    role: Role
    is_active: bool
    is_verified: bool


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    work_date: date
    check_in: datetime | None
    check_out: datetime | None
    status: AttendanceStatus
    is_late: bool
    late_minutes: int
    worked_minutes: int
    overtime_minutes: int
    geo_verified: bool


class DashboardStats(BaseModel):
    total_users: int
    total_departments: int
    present_today: int
    late_today: int
    absent_today: int
    on_leave_today: int
    avg_work_hours: float
    attendance_rate: float


class ChartSeries(BaseModel):
    labels: list[str]
    values: list[float]
