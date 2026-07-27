"""Регистрация всех роутеров бота."""
from aiogram import Dispatcher

from app.bot.handlers import (
    admin,
    attendance,
    auth,
    common,
    history,
    hr,
    leave,
    manager,
    qr,
    reports,
)


def register_handlers(dp: Dispatcher) -> None:
    # Порядок важен: сначала auth (перехват неавторизованных), потом остальные
    dp.include_router(common.router)
    dp.include_router(auth.router)
    dp.include_router(attendance.router)
    dp.include_router(qr.router)
    dp.include_router(history.router)
    dp.include_router(leave.router)
    dp.include_router(reports.router)
    dp.include_router(manager.router)
    dp.include_router(hr.router)
    dp.include_router(admin.router)
