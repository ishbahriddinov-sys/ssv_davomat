"""Централизованная конфигурация приложения (pydantic-settings)."""
from __future__ import annotations

from datetime import time
from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Приложение ----
    app_name: str = "MoH Attendance Bot"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"
    timezone: str = "Asia/Tashkent"
    default_language: str = "uz"

    # ---- Telegram ----
    bot_token: str = ""
    bootstrap_admins: str = ""

    # ---- База данных ----
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "attendance"
    postgres_user: str = "attendance"
    postgres_password: str = "attendance_pass"
    database_url: str | None = None

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None
    redis_enabled: bool = True   # на Render/бесплатном хосте без Redis → false

    # ---- Режим бота ----
    # polling — отдельный процесс (локально/VPS); webhook — внутри FastAPI (Render)
    bot_webhook_enabled: bool = False
    webhook_secret: str = ""
    # Создавать таблицы + первичные данные при старте (для хостинга без миграций)
    auto_init_db: bool = False
    # Render автоматически задаёт RENDER_EXTERNAL_URL; можно указать вручную
    render_external_url: str = ""
    public_base_url: str = ""

    # ---- Безопасность ----
    encryption_key: str = ""
    jwt_secret: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    # Разрешённые источники для CORS (через запятую). Пусто = только локальная панель.
    cors_origins: str = ""
    # Защита от перебора пароля
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300

    # ---- Геозона ----
    office_latitude: float = 41.311081
    office_longitude: float = 69.240562
    office_radius_meters: int = 250

    # ---- График ----
    work_day_start: str = "09:30"
    work_day_end: str = "18:00"
    late_threshold_minutes: int = 10
    standard_work_hours: int = 8

    # ---- QR ----
    qr_ttl_seconds: int = 120

    # ---- Telegram Mini App ----
    # Публичный HTTPS-адрес приложения (для кнопки мини-приложения).
    # Напр.: https://attendance.example.uz  или https URL туннеля.
    webapp_url: str = ""

    # ---- Admin ----
    admin_panel_port: int = 8000

    # ================= Производные значения =================
    @computed_field
    @property
    def sqlalchemy_dsn(self) -> str:
        if self.database_url:
            # Supabase/облако отдают postgresql:// — приводим к async-драйверу asyncpg
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_external_db(self) -> bool:
        """Внешняя БД (Supabase и т.п.) — требует SSL."""
        return bool(self.database_url)

    @property
    def base_url(self) -> str:
        """Публичный HTTPS-адрес приложения (для webhook и Mini App)."""
        return (self.render_external_url or self.public_base_url or "").rstrip("/")

    @property
    def effective_webapp_url(self) -> str:
        if self.webapp_url:
            return self.webapp_url
        if self.base_url:
            return f"{self.base_url}/api/webapp/"
        return ""

    @computed_field
    @property
    def sync_sqlalchemy_dsn(self) -> str:
        """Синхронный DSN для Alembic."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origin_list(self) -> List[str]:
        raw = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]
        if raw:
            return raw
        # Значение по умолчанию — только локальная панель (без wildcard+credentials)
        return [
            f"http://localhost:{self.admin_panel_port}",
            f"http://127.0.0.1:{self.admin_panel_port}",
        ]

    @property
    def bootstrap_admin_ids(self) -> List[int]:
        raw = (self.bootstrap_admins or "").replace(" ", "")
        return [int(x) for x in raw.split(",") if x.isdigit()]

    @property
    def work_start_time(self) -> time:
        h, m = self.work_day_start.split(":")
        return time(int(h), int(m))

    @property
    def work_end_time(self) -> time:
        h, m = self.work_day_end.split(":")
        return time(int(h), int(m))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
