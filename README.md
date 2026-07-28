# 🏥 Система учёта посещаемости — Министерство здравоохранения РУз

Современный Telegram-бот + REST API + веб-панель администратора для автоматического
учёта посещаемости сотрудников. Многоязычный интерфейс (🇺🇿 / 🇷🇺 / 🇬🇧),
геолокация, QR-коды, отчёты и дашборды.

---

## ✨ Возможности

| Модуль | Функции |
|--------|---------|
| **Авторизация** | Вход по корпоративному ID, подтверждение по телефону/OTP, 4 роли (Администратор, Руководитель, Сотрудник, HR) |
| **Перекличка (roll-call)** | Отметку посещаемости проводят **только Администратор и Оператор** через панель: «Пришёл / Не пришёл» на выбранную дату; для отсутствующих — причина и загрузка документа-доказательства (PDF/JPG/PNG/DOC). Авторасчёт опозданий |
| **Бот для сотрудников** | Рядовые сотрудники **не отмечаются сами** — им доступны только просмотр истории и заявки на отпуск |
| **Геозона** | Проверка нахождения в пределах территории Министерства (формула гаверсинуса) |
| **QR-код** | Ежедневный QR с ограниченным сроком жизни (по умолчанию 120 сек) |
| **История** | Посещения, опоздания, пропуски, отработанные часы |
| **Панель руководителя** | Кто пришёл / отсутствует / опоздал / в отпуске, статистика отдела |
| **Панель администратора** | CRUD сотрудников и отделов, назначение руководителей, экспорт, журнал действий |
| **HR-модуль** | Автоматический расчёт опозданий, прогулов, переработок, отпусков, больничных |
| **Уведомления** | Не отметил приход, опоздание, завершение дня, напоминание об уходе |
| **Отчёты** | Excel / PDF / CSV — ежедневные, недельные, месячные, по отделам и сотрудникам |
| **Дашборд** | Графики: посещаемость, опоздания, рейтинг отделов, динамика за месяц |
| **Безопасность** | RBAC, аудит-лог, шифрование ПДн (Fernet), 2FA (TOTP), резервное копирование |

---

## 🏗 Архитектура (модульная, SOLID)

```
app/
├── config.py               # централизованная конфигурация (pydantic-settings)
├── core/                   # ядро: enums, security (шифрование/JWT/2FA), logging
├── db/                     # SQLAlchemy: base, session, models, init_db (seed)
├── i18n/                   # интернационализация uz / ru / en
├── services/               # бизнес-логика (SOLID): attendance, qr, geo, hr,
│                           #   reports, notifications, dashboard, scheduler ...
├── bot/                    # Telegram-бот (aiogram 3.x)
│   ├── handlers/           #   auth, attendance, qr, history, leave,
│   │                       #   manager, hr, admin, reports, common
│   ├── keyboards/          #   reply + inline клавиатуры
│   ├── middlewares/        #   инъекция сессии БД и пользователя
│   ├── states.py           #   FSM-состояния
│   ├── loader.py           #   Bot / Dispatcher / Redis storage
│   └── main.py             #   точка входа (long polling)
├── api/                    # FastAPI REST API
│   ├── routers/            #   auth, users, departments, attendance,
│   │                       #   dashboard, reports, logs
│   ├── deps.py             #   зависимости (JWT / cookie / RBAC)
│   ├── schemas.py          #   Pydantic-схемы
│   └── main.py             #   точка входа FastAPI
└── admin/                  # веб-панель (Jinja2 + Chart.js, стиль GOV.UZ)
    ├── router.py
    ├── templates/
    └── static/             #   style.css, app.js
```

**Технологии:** Python 3.12 · FastAPI · aiogram 3.x · SQLAlchemy 2 (async) ·
PostgreSQL · Redis · Docker · APScheduler · openpyxl / reportlab · Chart.js.

### Таблицы БД
`users` · `departments` · `attendance` · `qr_sessions` · `leaves` ·
`notifications` · `action_logs` · `admin_users`

---

## 🚀 Быстрый старт (Docker)

```bash
# 1. Настроить окружение
cp .env.example .env
# Обязательно укажите BOT_TOKEN и сгенерируйте ключи:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # -> ENCRYPTION_KEY

# 2. Запустить весь стек
make up          # или: docker compose up -d

# 3. Проверить
docker compose logs -f
```

Сервисы после запуска:
- **API + веб-панель:** http://localhost:8000
- **Панель администратора:** http://localhost:8000/admin  (логин `admin` / пароль `admin123` — **смените!**)
- **Swagger (API-документация):** http://localhost:8000/docs
- **Telegram-бот:** работает в режиме long polling

Сервис `migrate` при старте создаёт таблицы и первичные данные автоматически.

### Демо-данные (тестовые сотрудники для переклички)

```bash
docker compose -p attendance run --rm api python -m app.db.seed_demo
```
Создаёт 4 отдела, 14 тестовых сотрудников и отдельный вход **оператора переклички**:
`rollcall` / `rollcall123`. Затем в панели → раздел **«Перекличка»**.
> ⚠️ `seed_demo` пересоздаёт схему (все данные будут удалены) — только для демо/теста.

---

## 🖥 Деплой на свой сервер (VPS) — production

Весь стек в Docker, данные (ПДн) остаются на вашем сервере. HTTPS — автоматически (Caddy + Let's Encrypt).

### Требования
- Linux-сервер (Ubuntu 22.04+) с публичным IP.
- Установлены **Docker** и **docker compose**.
- Домен (напр. `ssvdavomat.uz`), A-запись которого указывает на IP сервера.
- Открыты порты **80** и **443**.

### Шаги
```bash
# 1. Установить Docker (если ещё нет)
curl -fsSL https://get.docker.com | sh

# 2. Получить код
git clone https://github.com/ishbahriddinov-sys/ssv_davomat.git
cd ssv_davomat

# 3. Настроить окружение
cp .env.prod.example .env
nano .env          # заполнить: DOMAIN, BOT_TOKEN, POSTGRES_PASSWORD,
                   #            ENCRYPTION_KEY, SECRET_KEY, JWT_SECRET
# Сгенерировать ключи:
#   openssl rand -hex 32                                            -> SECRET_KEY / JWT_SECRET
#   python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"  -> ENCRYPTION_KEY

# 4. Запустить
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

# 5. Логи
docker compose -f docker-compose.prod.yml logs -f
```

После старта (Caddy выпустит сертификат за ~30 сек):
- **Панель:** `https://<ваш-домен>/admin` (`admin` / `admin123` — смените!)
- **Mini App:** кнопка «Давомат» в боте (бот работает в режиме polling).

> ⚠️ **Один бот — один токен.** Если раньше был запущен деплой на Render с тем же
> `BOT_TOKEN`, остановите его (или удалите webhook), иначе бот будет конфликтовать.
> Удалить webhook: `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"`.

### Обновление
```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Резервные копии БД
```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U attendance attendance | gzip > backup_$(date +%F).sql.gz
```

---

## ☁️ Бесплатный деплой: Render + Supabase

Приложение (FastAPI + панель + Mini App + Telegram-бот через **webhook**) работает
одним сервисом на бесплатном плане Render; база данных — бесплатный PostgreSQL Supabase.

### 1. База данных (Supabase)
1. Создайте проект на [supabase.com](https://supabase.com).
2. **Project Settings → Database → Connection string → URI**, скопируйте:
   `postgresql://postgres:[ПАРОЛЬ]@db.xxxx.supabase.co:5432/postgres`

### 2. Репозиторий
```bash
git init && git add . && git commit -m "init"
# создайте пустой репозиторий на GitHub и:
git remote add origin https://github.com/<вы>/ssv-davomat.git
git push -u origin main
```
`.env` в репозиторий не попадёт (в `.gitignore`) — секреты задаются в Render.

### 3. Render
1. [render.com](https://render.com) → **New → Blueprint** → выберите репозиторий
   (Render прочитает [`render.yaml`](render.yaml)).
2. В переменных окружения (Environment) задайте:
   - `BOT_TOKEN` — токен бота от @BotFather
   - `DATABASE_URL` — строка подключения Supabase (из шага 1)
   - `ENCRYPTION_KEY` — сгенерируйте:
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - (`SECRET_KEY`, `JWT_SECRET`, `WEBHOOK_SECRET` создаются автоматически)
3. **Deploy**. Render выдаст адрес вида `https://ssv-davomat.onrender.com`.

При старте автоматически: создаются таблицы и учётка `admin/admin123`, ставится
Telegram webhook и кнопка Mini App. Панель — `https://…onrender.com/admin`,
Mini App открывается кнопкой меню в боте.

> ⚠️ Бесплатный план Render «засыпает» после 15 мин простоя — первый запрос/сообщение
> после паузы отвечает с задержкой ~30–60 сек (Telegram повторит доставку). Для
> постоянной готовности используйте платный план или VPS.
> Смените пароль `admin` после первого входа.

---

## 💻 Локальный запуск (без Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # укажите БД, Redis, BOT_TOKEN

# поднять PostgreSQL и Redis (например, через Docker):
docker compose up -d db redis

python -m app.db.init_db          # создать таблицы + seed
make api                          # веб-панель + API  (http://localhost:8000)
make bot                          # Telegram-бот (в отдельном терминале)
make scheduler                    # планировщик уведомлений (в отдельном терминале)
```

---

## 🔐 Роли и доступ

| Роль | Возможности |
|------|-------------|
| **Сотрудник** | отметка прихода/ухода, QR, история, заявки на отпуск |
| **Руководитель** | + панель отдела, отчёты по своему отделу, генерация QR |
| **HR** | + HR-сводка, отчёты по всем, экспорт |
| **Администратор** | + управление сотрудниками/отделами, журнал действий, 2FA |

Первичные администраторы бота задаются в `.env` → `BOOTSTRAP_ADMINS` (Telegram ID через запятую).

---

## 🔒 Безопасность

- **Шифрование ПДн** — ФИО и телефон хранятся зашифрованными (Fernet, `ENCRYPTION_KEY`).
- **RBAC** — разграничение прав по ролям на уровне бота и API.
- **Аудит** — все значимые действия пишутся в `action_logs`.
- **2FA (TOTP)** — для администраторов (совместимо с Google Authenticator).
- **JWT** — авторизация веб-панели и API.
- **Резервное копирование** — `make backup` (pg_dump + ротация 14 копий).

- **Защита от перебора** — блокировка входа после `LOGIN_MAX_ATTEMPTS` неудач (Redis).
- **CORS** — только явный список источников (`CORS_ORIGINS`), без `*` при cookie-аутентификации.
- **Загрузка док-в** — проверка MIME/размера, безопасное имя файла, выдача как `attachment` + `X-Content-Type-Options: nosniff`.

### ✅ Чек-лист безопасности перед выкладкой в production

1. **Сменить пароли** учёток панели `admin` и `rollcall` (дефолтные — только для демо).
2. `DEBUG=false` — отключает эхо SQL в логах и подробные трейсбеки.
3. Задать собственные `SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY`
   (без `ENCRYPTION_KEY` при `DEBUG=false` приложение не стартует — это защита ПДн).
4. `CORS_ORIGINS` = точный адрес панели (напр. `https://attendance.minzdrav.uz`).
5. Работать только по **HTTPS** (тогда cookie автоматически получает флаг `Secure`).
6. В `docker-compose.yml` убрать проброс портов БД/Redis наружу (`5433`, `6380`) —
   доступ должен быть только внутри compose-сети.
7. Включить **2FA** для всех администраторов и операторов.
8. Не запускать `app.db.seed_demo` на боевой базе (он пересоздаёт схему).

---

## 🗄 Миграции (Alembic)

Первичная схема создаётся через `python -m app.db.init_db`.
Для эволюции схемы:

```bash
make revision m="add new field"   # автогенерация миграции
make migrate                      # применить
```

---

## 📊 REST API (основные эндпоинты)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/login` | вход администратора (JWT, поддержка 2FA через scope) |
| GET | `/api/dashboard/stats` | сводная статистика |
| GET | `/api/dashboard/trend` \| `/ranking` \| `/late` | данные графиков |
| GET/POST/PATCH/DELETE | `/api/users` | сотрудники |
| GET/POST/PATCH | `/api/departments` | отделы |
| GET | `/api/attendance` | посещаемость (фильтры по дате/сотруднику) |
| GET | `/api/reports/export?fmt=xlsx\|pdf\|csv` | экспорт отчёта |
| GET | `/api/logs` | журнал действий (только Администратор) |

Полная интерактивная документация — `/docs`.

---

## 🎨 UI

Минималистичный дизайн в корпоративных цветах Министерства здравоохранения
(белый · голубой · тёмно-синий), адаптивная вёрстка для мобильных устройств.

---

## 📁 Настройка геозоны и графика

В `.env`:
```
OFFICE_LATITUDE=41.311081
OFFICE_LONGITUDE=69.240562
OFFICE_RADIUS_METERS=250
WORK_DAY_START=09:00
WORK_DAY_END=18:00
LATE_THRESHOLD_MINUTES=10
QR_TTL_SECONDS=120
```
