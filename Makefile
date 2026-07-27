.PHONY: help build up down logs init migrate revision bot api scheduler backup fmt

help:
	@echo "make build     - собрать образы Docker"
	@echo "make up        - запустить весь стек (db, redis, api, bot, scheduler)"
	@echo "make down      - остановить стек"
	@echo "make logs      - логи всех сервисов"
	@echo "make init      - создать таблицы и первичные данные"
	@echo "make revision m='msg' - создать миграцию alembic (autogenerate)"
	@echo "make migrate   - применить миграции alembic"
	@echo "make backup    - резервная копия БД (pg_dump)"
	@echo "make bot/api/scheduler - локальный запуск отдельного сервиса"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

init:
	python -m app.db.init_db

revision:
	alembic revision --autogenerate -m "$(m)"

migrate:
	alembic upgrade head

backup:
	bash scripts/backup.sh

bot:
	python -m app.bot.main

api:
	uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

scheduler:
	python -m app.services.scheduler

fmt:
	python -m ruff check --fix app || true
