"""Точка входа FastAPI: REST API + веб-панель администратора."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin.router import router as admin_router
from app.api.routers import (
    attendance,
    auth,
    dashboard,
    departments,
    logs,
    reports,
    rollcall,
    users,
    webapp,
)
from app.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    app.state.bot = None
    app.state.dp = None
    scheduler = None

    # Создание таблиц + первичные данные (хостинг без отдельного шага миграций)
    if settings.auto_init_db:
        try:
            from app.db import init_db

            await init_db.create_tables()
            await init_db.seed()
        except Exception as exc:  # noqa: BLE001
            from app.core.logging import get_logger

            get_logger(__name__).error("auto_init_db: %s", exc)

    # Бот в режиме webhook (Render/бесплатный хост — один процесс)
    if settings.bot_webhook_enabled and settings.bot_token:
        from app.bot.webhook import (
            create_bot_and_dispatcher,
            setup_webhook,
            shutdown_webhook,
        )

        try:
            bot, dp = create_bot_and_dispatcher()
            app.state.bot, app.state.dp = bot, dp
            await setup_webhook(bot, dp)
        except Exception as exc:  # noqa: BLE001
            from app.core.logging import get_logger

            get_logger(__name__).error("webhook setup: %s", exc)
            app.state.bot = None

        # Фоновые напоминания (лучшие усилия; на «спящем» хосте могут пропускаться)
        if app.state.bot is not None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                from apscheduler.triggers.cron import CronTrigger

                from app.services import scheduler as sched

                scheduler = AsyncIOScheduler(timezone=settings.timezone)
                ws, we = settings.work_start_time, settings.work_end_time
                scheduler.add_job(sched.remind_not_checked_in,
                                  CronTrigger(day_of_week="mon-fri", hour=ws.hour,
                                              minute=(ws.minute + 15) % 60))
                scheduler.add_job(sched.remind_checkout,
                                  CronTrigger(day_of_week="mon-fri", hour=we.hour,
                                              minute=max(we.minute - 10, 0)))
                scheduler.add_job(sched.flush_notifications, "interval",
                                  minutes=1, args=[app.state.bot])
                scheduler.start()
            except Exception:  # noqa: BLE001
                pass

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    if app.state.bot is not None:
        from app.bot.webhook import shutdown_webhook

        await shutdown_webhook(app.state.bot)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Система учёта посещаемости — Министерство здравоохранения РУз",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,   # явный список, без wildcard при credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# REST API
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(attendance.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(rollcall.router)
app.include_router(webapp.router)
app.include_router(logs.router)

# Веб-панель администратора
app.include_router(admin_router)

# Статика панели
app.mount(
    "/static",
    StaticFiles(directory="app/admin/static"),
    name="static",
)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/telegram/status", tags=["telegram"])
async def telegram_status():
    """Диагностика webhook (без секретов)."""
    return {
        "bot_enabled": getattr(app.state, "bot", None) is not None,
        "webhook_mode": settings.bot_webhook_enabled,
        "base_url": settings.base_url or None,
        "webapp_url": settings.effective_webapp_url or None,
        "has_token": bool(settings.bot_token),
    }


@app.post("/telegram/webhook/{secret}", tags=["telegram"])
async def telegram_webhook(secret: str, request: Request):
    """Приём обновлений Telegram (webhook-режим)."""
    from aiogram.types import Update

    expected = settings.webhook_secret or "hook"
    if secret != expected:
        raise HTTPException(status_code=404, detail="Not found")
    # Дополнительная проверка секретного заголовка Telegram
    if settings.webhook_secret and request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token"
    ) != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    bot = getattr(app.state, "bot", None)
    dp = getattr(app.state, "dp", None)
    if bot is None or dp is None:
        raise HTTPException(status_code=503, detail="Bot not enabled")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
