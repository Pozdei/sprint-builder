# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sprint Builder — внутренний инструмент для формирования и прогнозирования спринтов на основе данных Jira. Бэкенд: FastAPI + SQLAlchemy + PostgreSQL. Фронтенд: React 19 + Vite + TypeScript + Tailwind. Многопользовательский: каждый lead-пользователь держит один или несколько именованных "конфигов" (команда, роли, направления, доска Jira) и работает в рамках активного конфига.

Развёртывание на новой машине/сервере, `.env`-переменные, бэкапы — в **README.md** (не дублируй сюда).

## Commands

### Backend (из `backend/`)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env         # заполнить JIRA_API_TOKEN и др.
alembic upgrade head
uvicorn app.main:app --reload --port 8000    # Swagger: :8000/docs
```
Новая миграция: `alembic revision -m "phaseNNN_<short-desc>"` (продолжая нумерацию фаз; НЕ timestamp), `upgrade`/`downgrade` дописать руками.

### Frontend (из `frontend/`)
```bash
npm install
npm run dev        # :5173, ходит в backend на :8000
npm run build      # tsc -b && vite build — это и есть typecheck
npm run lint       # eslint .
```

### Docker (из корня)
```bash
docker compose up -d --build          # первый запуск / любые изменения кода
docker compose up -d --build backend  # после правок только backend/app/*.py
docker logs sprint-builder-backend-1 --tail 20   # ждать "Application startup complete"
```
- **`docker restart` НЕ подхватывает код** — прод-compose COPY'ит backend в образ, нужен `--build`.
- Миграции прогоняются автоматически в entrypoint при каждом старте (`docker/backend-entrypoint.sh`).
- Если демон не запущен (Mac): `open -a Docker`, подождать `docker info`.
- Dev-оверлей с hot-reload backend (bind-mount + `--reload`, порт 8000 наружу): `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`. Фронт в Docker всегда статический — hot-reload фронта только через локальный `npm run dev`.

## Verification (как проверять свою работу)

- **Backend: тестов и линтера НЕТ** — не выдумывай `pytest`/`ruff`. Быстрая проверка: `venv/bin/python -m py_compile app/...` + импорт-смоук (`DATABASE_URL`/`JWT_SECRET` можно задать фиктивные через env). Локальный venv может отставать от requirements — при `ModuleNotFoundError` сначала `pip install -r requirements.txt`.
- **Frontend: `npm run build` — обязательный минимум** (это typecheck). В `npm run lint` ~2 десятка **ранее существовавших** ошибок (setState-in-effect и т.п. по всему проекту) — не пытайся чинить попутно, проверяй только что не добавил новых.
- Изменил `schemas/*.py` → руками синхронизируй `frontend/src/types/api.ts` (ручное зеркало Pydantic-схем).
- Финальная проверка фичи — пересборка в Docker и живой прогон (см. Docker выше). Визуальные изменения UI проверяй скриншотом, а не рассуждением о CSS.

## Architecture

### Backend layout
```
api/        — FastAPI роутеры (HTTP-слой, тонкий; epic.py — исторически толстый, не наращивай)
services/   — бизнес-операции (транзакции, проверки доступа)
sprint/     — чистая бизнес-логика и алгоритмы (без БД, без FastAPI)
db/         — SQLAlchemy-модели + репозитории (CRUD)
schemas/    — Pydantic-схемы запросов/ответов
jira/       — HTTP-клиент Jira
telegram/   — Telegram-клиент (дайджесты)
core/       — настройки (.env), security (JWT/bcrypt/Fernet), i18n
```
Слой вызовов: `api/*` → `services/*` → (`sprint/*` | `db/*repository.py`). `sprint/*` модули принимают только plain dict/dataclass (`SprintConfig`, `config_snapshot`) — **никогда ORM-объекты**, поэтому один и тот же scheduling работает и для живого конфига, и для замороженных снапшотов истории.

Все защищённые роутеры висят на `Depends(get_current_user)` (JWT, см. `api/deps.py`). Роли: `admin` (видит все конфиги, `/admin/*`) и `lead` (только свои конфиги через `active_config_id` на `User`).

### Domain model — три раздела фронтенда, общий "конвейер" под капотом

1. **Спринт** (`SprintPage`, `api/sprint.py` → `services/sprint_service.py`) — собрать кандидатов из Jira-досок конфига, разложить по людям (`collect_candidates` / `allocate` в `sprint/logic.py`), при сохранении — `Sprint` (draft) с `SprintTask[]`.
2. **История** (`HistoryPage`, `api/sprints.py` → `services/sprints_service.py`) — approved/closed спринты. Approve фиксирует `config_snapshot` и `owner_stats_snapshot`. Задачи, появившиеся в Jira после approve — "врывы" (`Sprint.intrusions`), подсвечиваются при closure.
3. **Прогноз реализации** (`EpicForecastPage`, `api/epic.py` → `sprint/epic_forecast.py`) — расписать весь оставшийся pipeline без бюджета. Источник задач — **либо** эпик(и)/задача из Jira, **либо** approved-спринт из истории (`effective_key = "sprint-{num}"`, задачи по ключам из снапшота, алгоритм тот же). `use_history=True` достраивает прошлые фазы из Jira changelog (`epic_history.py`) — единая шкала "прошлое + будущее".

Все три рисуют один Гант (`GanttChart.tsx` + `compute_gantt_schedule` в `sprint/gantt.py`); различие — источник задач и наличие бюджета.

### Pipeline / directions (ядро бизнес-логики)

Задача матчится в **направление** (`ConfigDirection`: `labels` + `work_types`) по Jira-меткам. `work_types` — упорядоченный список этапов, напр. `["analytics", "design", "development", "code_review", "testing"]`. Каждый `work_type` маппится на:
- **bucket** — отображаемое имя этапа (рус.): Анализ / Дизайн / Разработка / Код-ревью / Дизайн-ревью / Тестирование / Релиз. Единый источник — `sprint/buckets.py` (BE) и `lib/bucket-color.ts` (FE); не заводи новые маппинги.
- **role** — исполнитель (analyst/developer/designer/developer_lead/...), переопределяется per-direction через `role_overrides`.

Внутри задачи этапы строго последовательны по позиции в `work_types`. На Ганте одна Jira-задача = несколько последовательных баров-этапов; в обсуждениях это называется **"колбаска"** (одна колбаска = один Jira-key).

Этапы code_review/design_review/testing в разделе "Спринт" генерируются **после** `allocate()` функцией `derive_pipeline_tasks` — не конкурируют за бюджет часов. В прогнозе бюджета нет — все этапы генерируются сразу.

### Cross-task dependencies & scheduling (`sprint/gantt.py`)

`compute_gantt_schedule()` — event-driven scheduler по очереди каждого исполнителя:
- **Pipeline-зависимости** — внутри задачи, по позиции bucket'а в pipeline направления.
- **FS-зависимости между задачами** — пользовательские `{from_key, to_key}` (задача → задача целиком): B стартует после **всех** этапов A. Хранение: `Sprint.task_dependencies` (JSON) для Спринта/Истории; `EpicTaskDependency` (таблица, `config_id + epic_key`) для Прогноза — `epic_key` может быть и псевдо-ключом `sprint-N`.
- **Отпуска** (`EmployeeVacation`, уровень конфига) — блокируют часы исполнителя.
- **Стартовая задача** (`EmployeeRootTask`) — Start-Start якорь: первой в очереди исполнителя, не ломая pipeline.

Узел графа зависимостей везде — тюпл `(key, bucket)` (по соглашению, не named type). `all_preds: dict[tuple, list[tuple]]` — единая структура для pipeline- и FS-зависимостей.

Общие входы планировщика для спринта (deps + vacations + root tasks) собирает `sprints_service.assemble_gantt_inputs()` — используй его, а не собирай руками.

### Снапшоты

`SprintGanttSnapshot` — снимок Ганта, привязан **либо** к `sprint_id` (история), **либо** к `config_id + epic_key` (прогноз) — общий механизм. `EpicForecastSnapshot` — ежедневная сводка прогноза, одна запись на день (upsert), pinned-записи не перезаписываются.

### Jira-подключение per-конфиг

`Config` может хранить свои `jira_base_url`/`jira_email`/`jira_api_token_enc` (Fernet, ключ из `JWT_SECRET` — `core/security.py`); если что-то из трёх пусто — глобальные `.env`-настройки. `jira/client.py: client` — proxy над `contextvars.ContextVar`: `api/deps.py: get_jira_client` (async-генератор — **обязательно async**, иначе set/reset contextvar разъедутся по Context-копиям тред-пула с `ValueError`) на каждый запрос привязывает `JiraClient` активного конфига. Старый код `from app.jira.client import client; client.get(...)` работает как есть. Токены в API write-only (только флаг `*_token_set`). Telegram-токен устроен так же: per-конфиг `telegram_bot_token_enc`, fallback — env `TELEGRAM_BOT_TOKEN`.

### Frontend

Без роутера — страница в `location.hash` (`useHashPage` в `App.tsx`: `#/sprint`, `#/history`, `#/forecast`, `#/settings`, `#/docs`, `#/admin`). `api/*-client.ts` — тонкие axios-обёртки 1:1 к роутерам; `types/api.ts` — ручное зеркало Pydantic-схем. `ConfigSwitcher` бампает `configEpoch` → через `key=` пересоздаёт страницы (полная перезагрузка вместо инвалидации).

## Conventions / DRY

Похожая логика между разделами (History ↔ Forecast) выносится в общий hook/компонент/функцию, а не копипастится. Уже существующие общие механизмы — используй их:

- `hooks/useGanttSnapshots.ts`: `useGanttSnapshots` + `useGanttSnapshotApi(scope, fns)` — снимки Ганта на обеих страницах; `hooks/useRootTasks.ts` — стартовые задачи.
- `sprint/logic.py: sprint_num_from_name(name)` — единственный парсер номера спринта из имени Jira-спринта.
- `db/repository.py: _replace_collection()` — паттерн перезаписи коллекций конфига (clear → flush → append).
- `services/sprints_service.py: _get_sprint_checked()` — загрузка спринта с проверками (404 / доступ / статус) для всех переходов статуса.
- `api/epic.py: _uniq()`, `_dep_to_dict()` — дедуп с сохранением порядка, конвертация зависимостей.
- i18n ошибок бэка: per-модуль `_MSG: dict` + `_t = make_translator(_MSG)` (`core/i18n.py`), язык — из `Depends(get_lang)`.
- Сервисы кидают доменные исключения (`SprintNotADraftError`, ...) — роутер маппит их в HTTP-коды; не кидай `HTTPException` из сервисов.
