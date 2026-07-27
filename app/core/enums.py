"""Перечисления ролей и статусов."""
from __future__ import annotations

import enum


class Role(str, enum.Enum):
    ADMIN = "admin"          # Администратор
    MANAGER = "manager"      # Руководитель
    EMPLOYEE = "employee"    # Сотрудник
    HR = "hr"                # HR


# Иерархия прав (для проверки доступа): чем выше — тем больше прав
ROLE_LEVEL = {
    Role.EMPLOYEE: 1,
    Role.MANAGER: 2,
    Role.HR: 2,
    Role.ADMIN: 3,
}


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"        # Присутствует (отметил приход)
    COMPLETED = "completed"    # Рабочий день завершён
    ABSENT = "absent"          # Отсутствует / прогул
    LATE = "late"              # Опоздал
    ON_LEAVE = "on_leave"      # В отпуске
    SICK = "sick"              # На больничном


class CheckMethod(str, enum.Enum):
    BUTTON = "button"
    QR = "qr"
    GEO = "geo"
    MANUAL = "manual"          # добавлено администратором


class LeaveType(str, enum.Enum):
    VACATION = "vacation"      # Отпуск
    SICK = "sick"              # Больничный
    UNPAID = "unpaid"          # За свой счёт
    BUSINESS_TRIP = "trip"     # Командировка


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class NotificationType(str, enum.Enum):
    NOT_CHECKED_IN = "not_checked_in"
    LATE = "late"
    DAY_COMPLETED = "day_completed"
    CHECKOUT_REMINDER = "checkout_reminder"
    LEAVE_REQUEST = "leave_request"
    SYSTEM = "system"
