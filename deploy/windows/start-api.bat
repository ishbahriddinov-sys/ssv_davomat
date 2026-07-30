@echo off
REM Запуск веб-приложения (панель + Mini App + API) на Windows.
cd /d "%~dp0\..\.."
call .venv\Scripts\activate.bat
python -m app.db.init_db
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
