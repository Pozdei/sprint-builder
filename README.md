# Sprint Builder

Внутренний инструмент для формирования и прогнозирования спринтов на основе данных Jira:
сбор кандидатов с досок, раскладка по людям и этапам конвейера (аналитика → дизайн →
разработка → ревью → тестирование), диаграмма Ганта с зависимостями и отпусками,
история утверждённых спринтов, прогноз реализации эпиков, Telegram-дайджест.

**Стек**: FastAPI + SQLAlchemy + PostgreSQL (backend), React 19 + Vite + TypeScript +
Tailwind (frontend), Caddy (reverse proxy + HTTPS), Docker Compose.

---

## Развёртывание на новой машине / сервере

Нужен только **Docker** (Desktop на Mac/Windows или Engine + compose-plugin на Linux).
Ни Python, ни Node на хосте не требуются — всё собирается в образах.

### 1. Получить код

```bash
git clone <repo-url> sprint-builder
cd sprint-builder
```

(или скопировать директорию проекта целиком, без `backend/venv` и `frontend/node_modules`)

### 2. Заполнить `.env`

```bash
cp .env.example .env
```

| Переменная | Что это |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Креды БД внутри compose. Пароль — длинный случайный. |
| `JIRA_BASE_URL` | Адрес Jira, напр. `https://yourcompany.atlassian.net` |
| `JIRA_EMAIL` / `JIRA_API_TOKEN` | Учётка Jira + API-токен ([создать токен](https://id.atlassian.com/manage-profile/security/api-tokens)). Это глобальный fallback — каждый конфиг может задать своё подключение в UI (Settings → «Подключение к Jira»). |
| `JWT_SECRET` | Секрет подписи JWT **и** ключ шифрования токенов в БД. Сгенерировать: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. ⚠️ При смене секрета зашифрованные per-конфиг токены (Jira/Telegram) перестанут расшифровываться — их придётся ввести заново. |
| `JWT_EXPIRE_HOURS` | Время жизни сессии (по умолчанию 24). |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Первый администратор — создаётся автоматически при первом старте бэка. |
| `TELEGRAM_BOT_TOKEN` | Опционально. Токен бота от @BotFather для ежедневных дайджестов (chat_id и расписание — per-конфиг в UI). Пусто = дайджест выключен. |
| `DOMAIN` | Локально: `:80`. На сервере: домен, напр. `sprint.yourcompany.com` — Caddy сам выпустит Let's Encrypt сертификат (нужны открытые порты 80 и 443 и A-запись на сервер). |

### 3. Запустить

```bash
docker compose up -d --build
```

Миграции БД применяются автоматически при каждом старте backend-контейнера
(`docker/backend-entrypoint.sh`), отдельного шага не нужно.

Проверка: `docker logs sprint-builder-backend-1 --tail 20` — ждать
`Application startup complete`.

### 4. Войти

Открыть `http://localhost` (или `https://<DOMAIN>`), войти под
`ADMIN_EMAIL`/`ADMIN_PASSWORD`. Дальше: завести lead-пользователей в разделе Admin,
под lead-пользователем создать конфиг (команда, роли, направления, доски Jira)
в Settings.

---

## Обновление

```bash
git pull
docker compose up -d --build      # пересборка + автоматические миграции
```

`docker restart` изменения кода **не** подхватывает — код вшивается в образ на
стадии сборки, нужен именно `--build`.

## Бэкап и перенос данных

Все данные — в named volume `pg_data`. Бэкап/восстановление:

```bash
# Дамп (директория backups/ в .gitignore — дампы не коммитятся)
docker exec sprint-builder-postgres-1 pg_dump -U sprint_app sprint_builder \
  > backups/sprint_builder_$(date +%Y-%m-%d).sql

# Восстановление на новой машине (после docker compose up -d postgres)
docker exec -i sprint-builder-postgres-1 psql -U sprint_app sprint_builder \
  < backups/sprint_builder_YYYY-MM-DD.sql
```

Перенос из локального (не-Docker) Postgres: `./scripts/migrate-from-local.sh`.

⚠️ `docker compose down -v` удаляет volume вместе со всеми данными.
Обычная остановка — `docker compose down` (без `-v`).

Для переноса на другую машину достаточно: код проекта + `.env` + дамп БД.
Если `JWT_SECRET` в `.env` сохранён тем же — переедут и зашифрованные
per-конфиг токены.

---

## Разработка

### Backend с hot-reload (Docker)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Bind-mount `backend/` + `--reload`, API открыт напрямую на `:8000`
(Swagger: http://localhost:8000/docs).

### Backend локально (без Docker)

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env           # заполнить; DATABASE_URL — на свой Postgres
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend с hot-reload

Фронт в Docker всегда статический; для hot-reload — локально:

```bash
cd frontend
npm install
npm run dev        # :5173, ходит в API на :8000
```

Проверка перед коммитом: `npm run build` (tsc + vite) и `npm run lint`.

Подробности архитектуры и конвенции — в [CLAUDE.md](CLAUDE.md).
