@echo off
REM Запуск Telegram-бота (polling) на Windows.
cd /d "%~dp0\..\.."
call .venv\Scripts\activate.bat
python -m app.bot.main
