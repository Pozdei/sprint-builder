# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sprint Builder — внутренний инструмент для формирования и прогнозирования спринтов на основе данных Jira. Бэкенд: FastAPI + SQLAlchemy + PostgreSQL. Фронтенд: React 19 + Vite + TypeScript + Tailwind. Многопользовательский: каждый lead-пользователь держит один или несколько именованных "конфигов" (команда, роли, направления, доска Jira) и работает в рамках активного конфига.

## Commands

### Backend (из `backend/`)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # заполнить JIRA_API_TOKEN и др. (см. .env.example в корне)
alembic upgrade head            # применить миграции
uvicorn app.main:app --reload --port 8000
```
Swagger UI: http://localhost:8000/docs

Новая миграция: `alembic revision -m "phaseNNN_..."` (см. конвенцию имён ниже), затем дописать `upgrade`/`downgrade` руками.

Нет тестов и линтера в backend — не выдумывай команды `pytest`/`ruff`, их не существует в проекте.

### Frontend (из `frontend/`)
```bash
npm install
npm run dev        # dev-сервер на :5173, ходит в backend на :8000
npm run build       # tsc -b && vite build — это и есть typecheck
npm run lint        # eslint .
```

### Docker (из корня репозитория)
Прод-compose **не** делает bind-mount кода backend — он COPY'ится в образ на стадии сборки.
```bash
docker compose up -d --build          # первый запуск / любые изменения кода
docker compose up -d --build backend  # после правок только backend/app/*.py
docker logs sprint-builder-backend-1 --tail 20   # проверить, что поднялся (ждать "Application startup complete")
```
**`docker restart` НЕ подхватывает изменения** — нужен именно `--build`. Alembic-миграции прогоняются автоматически в entrypoint при каждом старте контейнера (`docker/backend-entrypoint.sh`).

Dev-оверлей с hot-reload backend (bind-mount + `--reload`, открыт порт 8000):
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
Фронт в Docker всегда собирается статически (Caddy); для hot-reload фронта запускай `npm run dev` локально отдельно.

## Architecture

### Backend layout
```
api/        — FastAPI роутеры (HTTP-слой, тонкий)
services/   — бизнес-операции поверх репозиториев + бизнес-логики (транзакции, проверки доступа)
sprint/     — чистая бизнес-логика и алгоритмы (без БД, без FastAPI)
db/         — SQLAlchemy-модели + репозитории (CRUD)
schemas/    — Pydantic-схемы запросов/ответов
jira/       — HTTP-клиент Jira
core/       — настройки (.env) и security (JWT/bcrypt)
```
Слой вызовов: `api/*` → `services/*` → (`sprint/*` бизнес-логика | `db/*repository.py` CRUD). `sprint/*` модули принимают только plain dict/dataclass (`SprintConfig`, `config_snapshot`) — никогда ORM-объекты, поэтому одна и та же логика scheduling используется и для живого конфига, и для замороженных снапшотов истории.

Все защищённые роутеры (`sprint`, `sprints`, `configs`, `export`, `admin`, `jira`, `epic`) висят на `Depends(get_current_user)` — JWT в заголовке, см. `api/deps.py`. Роли пользователя: `admin` (доступ к `/admin/*`, видит все конфиги) и `lead` (работает только со своими конфигами через `active_config_id` на `User`).

### Domain model — три раздела фронтенда, общий "конвейер" под капотом

1. **Спринт** (`SprintPage`, `api/sprint.py` → `services/sprint_service.py`) — собрать кандидатов на ближайший спринт из Jira-досок текущего конфига, разложить по людям (`collect_candidates` / `allocate` в `sprint/logic.py`), при сохранении — `Sprint` (draft) с `SprintTask[]`.
2. **История** (`HistoryPage`, `api/sprints.py` → `services/sprints_service.py`) — approved/closed спринты. Approve фиксирует `config_snapshot` (конфиг на момент утверждения) и `owner_stats_snapshot`. После approve в Jira могут появиться новые задачи — это "врывы" (`Sprint.intrusions`), отдельно подсвечиваются при closure.
3. **Прогноз реализации** (`EpicForecastPage`, `api/epic.py` → `sprint/epic_forecast.py`) — расписать весь оставшийся pipeline задач до завершения, без бюджетного ограничения. Источник задач — **либо** эпик/JQL-запрос из Jira, **либо** утверждённый (`status="approved"`) спринт из истории (тогда `effective_key = "sprint-{num}"` и задачи берутся по ключам из снапшота спринта, но прогоняются тем же алгоритмом). `use_history=True` достраивает прошлые фазы из Jira changelog (`epic_history.py`) перед прогнозом остатка — единая временная шкала "прошлое + будущее".

Все три раздела рисуют один и тот же Гант (`GanttChart.tsx` + `compute_gantt_schedule` в `sprint/gantt.py`), различается только то, откуда берётся список задач и есть ли бюджет.

### Pipeline / directions (ядро бизнес-логики)

Задача матчится в **направление** (`ConfigDirection`: `labels` + `work_types`) по Jira-меткам. `work_types` — упорядоченный список этапов конвейера, например `["analytics", "design", "development", "code_review", "testing"]`. Каждый `work_type` маппится на:
- **bucket** — отображаемое имя этапа (рус.): Анализ / Дизайн / Разработка / Код-ревью / Дизайн-ревью / Тестирование / Релиз (`_WORK_TYPE_TO_BUCKET` в `gantt.py`, `_WORK_TYPE_INFO` в `logic.py`),
- **role** — кто исполняет (analyst/developer/designer/developer_lead/designer_lead/...), может быть переопределена per-direction через `role_overrides`.

Внутри одной задачи этапы строго последовательны по позиции в `work_types` (pipeline-зависимость "шаг B начинается не раньше шага A для того же ключа"). На диаграмме Ганта одна Jira-задача рисуется как несколько последовательных баров-этапов — в обсуждении с пользователем это называют "колбаской"; именно одна "колбаска" = один Jira-key, разбитый на этапы.

Этапы code_review/design_review/testing для post-allocation сценария (раздел "Спринт") генерируются отдельно после `allocate()` функцией `derive_pipeline_tasks` — они не участвуют в конкурсе за бюджет часов, как обычные кандидаты. В прогнозе (раздел 3) все этапы, включая будущие, генерируются сразу — там нет бюджета.

### Cross-task dependencies & scheduling (`sprint/gantt.py`)

`compute_gantt_schedule()` — event-driven scheduler по очереди каждого исполнителя:
- **Pipeline-зависимости** — внутри задачи, по позиции bucket'а в pipeline направления (см. выше).
- **FS-зависимости между задачами** — пользовательские, хранятся как `{from_key, to_key}` (целиком задача → задача, **не** по этапам): `task B` стартует не раньше, чем закончатся **все** этапы `task A`. Резолвятся в `(key, bucket)`-пары через `last_stage_of_key`/`first_stage_of_key`. Хранение: `Sprint.task_dependencies` (JSON, per-спринт) для раздела "Спринт"/"История"; `EpicTaskDependency` (таблица, per `config_id` + `epic_key`) для "Прогноза" — `epic_key` там может быть как реальный Jira-ключ, так и псевдо-ключ `sprint-N`.
- **Отпуска** (`EmployeeVacation`, уровень конфига, не спринта) — блокируют часы конкретного исполнителя; учитываются и в реальных задачах, и при заполнении пробелов псевдо-задачами.
- **Стартовая задача** (`EmployeeRootTask`) — Start-Start якорь: задача встаёт первой в очереди исполнителя, не нарушая pipeline-зависимости.

Внутреннее представление узла графа зависимостей везде — тюпл `(key, bucket)` (не named type, просто `tuple[str, str]` по соглашению). `all_preds: dict[tuple, list[tuple]]` — единая структура и для pipeline-, и для FS-зависимостей.

### Снапшоты

`SprintGanttSnapshot` — статический снимок Ганта, привязан **либо** к `sprint_id` (история), **либо** к `config_id + epic_key` (прогноз) — общий механизм для обоих разделов. `EpicForecastSnapshot` — ежедневная сводка прогноза (даты/часы/cost), одна запись на день, перезаписывается при повторном построении в тот же день.

### Jira-подключение per-конфиг

`Config` может хранить свои `jira_base_url`/`jira_email`/`jira_api_token_enc` (токен — Fernet-шифрование, ключ выводится из `JWT_SECRET`, см. `core/security.py: encrypt_secret/decrypt_secret`); если хотя бы одно из трёх полей пусто — используются глобальные `.env`-настройки (`core/config.py: settings`). `jira/client.py` хранит `client` как proxy-объект над `contextvars.ContextVar`: на каждый запрос `api/deps.py: get_jira_client` (async-генератор — **обязательно async**, иначе set/reset contextvar попадут в разные Context-копии тред-пула и упадут с `ValueError`) резолвит нужный `JiraClient` через `client_for_config(config)` и привязывает к контексту запроса. За счёт этого весь старый код (`from app.jira.client import client; client.get(...)`) не менялся — он просто стал видеть креды активного конфига вместо одного глобального синглтона. UI — секция «Подключение к Jira» в Settings; токен write-only (не возвращается, только флаг `jira_api_token_set`).

### Frontend

Без роутера — страница хранится в `location.hash` (`useHashPage` в `App.tsx`, формат `#/sprint`, `#/history`, `#/forecast`, `#/settings`, `#/docs`, `#/admin`). `api/*-client.ts` — тонкие axios-обёртки 1:1 к backend-роутерам; `types/api.ts` — ручное зеркало Pydantic-схем (синхронизировать руками при изменении `schemas/*.py`). `ConfigSwitcher` меняет активный конфиг и бампает `configEpoch`, который через `key=` пересоздаёт страницы (полная перезагрузка данных вместо точечной инвалидации).

### Migrations

Имена в основном `2026_phaseNNN_<short-desc>.py` (не дата создания — последовательность фаз разработки), кроме нескольких самых старых файлов с timestamp-форматом по умолчанию из `alembic.ini` (`file_template`). Создавай новые в стиле `phaseNNN`, продолжая нумерацию.
