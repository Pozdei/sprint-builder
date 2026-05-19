# Patch 2.9 — Docker

## Что в патче

```
docker-compose.yml            # прод
docker-compose.dev.yml        # оверлей с hot reload
docker/backend.Dockerfile     # multi-stage сборка бэка
docker/frontend.Dockerfile    # Vite build + Caddy
docker/Caddyfile              # роутинг /api → backend, остальное — статика
docker/backend-entrypoint.sh  # ждать БД → миграции → uvicorn
backend-requirements.txt      # список зависимостей бэка для образа
.env.example                  # шаблон переменных
.dockerignore                 # что не тащить в build context
scripts/migrate-from-local.sh # перенос данных из локального Postgres в Docker
gitignore.example             # подсказка что добавить в .gitignore
```

## Установка

1. Распакуй патч в корень проекта:

       cd ~/Dev
       unzip -o ~/Downloads/sprint-builder-patch-2.9.zip -d sprint-builder/

   После распаковки в корне проекта (`~/Dev/sprint-builder/`) должны быть:
   - `docker-compose.yml`
   - `docker-compose.dev.yml`
   - `docker/`
   - `scripts/`
   - `.env.example`
   - `.dockerignore`

2. Положи requirements.txt в backend:

       cp backend-requirements.txt backend/requirements.txt

   Сравни с тем, что у тебя сейчас (`backend/requirements.txt` — там скорее
   всего то же самое). Если у тебя есть свои зависимости, добавь их.

3. Скопируй .env:

       cp .env.example .env

   Открой `.env` и заполни:
   - `POSTGRES_PASSWORD` — придумай длинный пароль.
   - `JIRA_*` — твои текущие из `backend/.env`.
   - `JWT_SECRET` — `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD` — твои текущие из `backend/.env`.
   - `DOMAIN=:80` — для локалки. Когда будет домен — впиши его.

4. Установи Docker Desktop (если ещё нет):
   https://www.docker.com/products/docker-desktop/

## Запуск (первый раз)

### Вариант 1 — Чистая БД

       docker compose up -d --build

После build — открой `http://localhost`. Залогинься под `ADMIN_EMAIL` /
`ADMIN_PASSWORD` из `.env` — он создастся при первом старте бэкенда.

### Вариант 2 — Перенос локальных данных

Если у тебя есть локальный Postgres с данными, которые хочешь сохранить:

       chmod +x scripts/migrate-from-local.sh
       ./scripts/migrate-from-local.sh

Он:
1. Сделает дамп локального `sprint_builder` через `pg_dump`.
2. Поднимет Docker `postgres`.
3. Загрузит дамп.

После этого:

       docker compose up -d --build

И открой `http://localhost`. Логин/пароль — те же, что были у тебя локально.

## Команды

```bash
# Старт (после первого build)
docker compose up -d

# Логи бэка
docker compose logs -f backend

# Логи фронта (Caddy)
docker compose logs -f frontend

# Зайти в БД
docker compose exec postgres psql -U sprint_app -d sprint_builder

# Стоп (данные сохранятся)
docker compose down

# Стоп + удалить ВСЕ ДАННЫЕ
docker compose down -v
```

## Dev-режим (hot reload бэка)

       docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

В этом режиме:
- Bind-mount `./backend` в контейнер.
- uvicorn с `--reload`.
- Порт 8000 проброшен напрямую — Swagger на `http://localhost:8000/docs`.

Фронт работает как в проде. Если хочешь hot reload фронта — запускай
**локально** в отдельном терминале:

       cd frontend
       npm run dev
       # → http://localhost:5173

Этот dev-server смотрит в http://localhost:8000 — это API, проброшенный
из Docker.

## Деплой на сервер (когда будет)

1. Скопируй проект на сервер.
2. На сервере создай `.env` (как в пункте 3 установки), но:

       DOMAIN=sprint.yourcompany.com

3. Убедись, что у домена A-запись смотрит на IP сервера.

4. Открой 80 и 443 на файрволе сервера.

5. Запусти:

       docker compose up -d --build

Caddy сам выпустит сертификат через Let's Encrypt и будет его обновлять.

## Что НЕ работает в Docker (известно)

- Если у Caddy не получится получить сертификат (например, домен не указывает
  на сервер) — он будет логать ошибки, но контейнер не упадёт. Сам сайт по
  HTTPS отдаваться не будет. Проверь логи: `docker compose logs frontend`.

- Если бэк не может подключиться к БД — entrypoint попробует 30 раз
  с интервалом 2 секунды (60 секунд), потом упадёт. Это значит, postgres
  не успел подняться. Перезапусти: `docker compose restart backend`.

- Все миграции применятся автоматически при старте бэка. Не запускай
  `alembic upgrade head` вручную внутри контейнера — иначе можешь словить
  гонку с auto-миграцией.

## После переноса — старый локальный stack

Локальный uvicorn и Postgres могут продолжать работать параллельно с Docker:
- Docker слушает 80/443 (и 8000 в dev).
- Локальный Postgres — 5432 (если он запущен).

Если хочешь освободить ресурсы:

       brew services stop postgresql@16
       # uvicorn — Ctrl+C в его терминале
