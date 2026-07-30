# 🪟 Запуск на Windows-сервере (без Docker)

Нативная установка: **Python 3.12 + PostgreSQL + Caddy** (авто-HTTPS).
Бот — режим polling, Redis не нужен (FSM в памяти).

---

## 1. Установить программы (один раз)

1. **Python 3.12** — https://www.python.org/downloads/windows/
   При установке отметьте ☑ «Add Python to PATH».
2. **PostgreSQL 16** — https://www.postgresql.org/download/windows/
   Запомните пароль пользователя `postgres`.
3. **Caddy для Windows** — https://caddyserver.com/download (файл `caddy_windows_amd64.exe`).
   Переименуйте в `caddy.exe` и положите в папку `deploy\windows`.

---

## 2. Создать базу данных

Откройте **SQL Shell (psql)** и выполните:
```sql
CREATE DATABASE attendance;
CREATE USER attendance WITH PASSWORD 'ПридумайтеПароль';
GRANT ALL PRIVILEGES ON DATABASE attendance TO attendance;
```

---

## 3. Получить код и настроить

```powershell
cd C:\
git clone https://github.com/ishbahriddinov-sys/ssv_davomat.git
cd ssv_davomat

# виртуальное окружение + зависимости
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# файл настроек
copy .env.prod.example .env
notepad .env
```

В `.env` заполнить (для Windows):
```
DOMAIN=ssvdavomat.uz
DEBUG=false
BOT_TOKEN=<токен от @BotFather>
BOT_WEBHOOK_ENABLED=false
WEBAPP_URL=https://ssvdavomat.uz/api/webapp/

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=attendance
POSTGRES_USER=attendance
POSTGRES_PASSWORD=ПридумайтеПароль

REDIS_ENABLED=false

# python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=<сгенерировать>
SECRET_KEY=<любая длинная строка>
JWT_SECRET=<любая длинная строка>
```

Сгенерировать `ENCRYPTION_KEY`:
```powershell
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
```

---

## 4. Запустить (3 окна)

Домен `ssvdavomat.uz` должен указывать (A-запись) на IP сервера, порты **80/443** открыты.

- Двойной клик **`deploy\windows\start-api.bat`**   — панель + Mini App (создаёт таблицы)
- Двойной клик **`deploy\windows\start-bot.bat`**   — Telegram-бот
- Двойной клик **`deploy\windows\start-caddy.bat`** — HTTPS (выпустит сертификат ~30 сек)

Готово:
- Панель: `https://ssvdavomat.uz/admin`  (`admin` / `admin123` — смените!)
- Mini App: кнопка «Давомат» в боте.

---

## 5. Автозапуск как службы (чтобы работало после перезагрузки)

Скачайте **NSSM** (https://nssm.cc/download) и зарегистрируйте службы:
```powershell
nssm install SSV-API    "C:\ssv_davomat\deploy\windows\start-api.bat"
nssm install SSV-Bot    "C:\ssv_davomat\deploy\windows\start-bot.bat"
nssm install SSV-Caddy  "C:\ssv_davomat\deploy\windows\start-caddy.bat"
nssm start SSV-API
nssm start SSV-Bot
nssm start SSV-Caddy
```

---

## ⚠️ Важно
- **Один токен — один бот.** Перед запуском отключите Render (удалите webhook), иначе конфликт:
  `curl "https://api.telegram.org/bot<ТОКЕН>/deleteWebhook"`
- Тест локально (без домена): панель — `http://localhost:8000/admin`. Но Mini App
  в Telegram требует HTTPS-домен (шаг с Caddy).
- Резервная копия БД:
  `"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U attendance attendance > backup.sql`
