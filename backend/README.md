# Sprint Builder — Backend

FastAPI-приложение для формирования спринта аналитиков на основе данных Jira.

## Запуск (локально)

```bash
# 1) Виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 2) Зависимости
pip install -r requirements.txt

# 3) Настройка
cp .env.example .env
# открой .env, подставь свой JIRA_API_TOKEN

# 4) Старт (включи VPN заранее)
uvicorn app.main:app --reload --port 8000
```

После старта:
- Swagger UI: http://localhost:8000/docs
- ReDoc:      http://localhost:8000/redoc

## Структура

```
app/
├── main.py              FastAPI entrypoint
├── core/config.py       Настройки (.env)
├── jira/client.py       Клиент Jira
├── sprint/config.py     Конфиг формирования спринта (значения по умолчанию)
├── sprint/logic.py      Бизнес-логика (collect_candidates, allocate)
└── api/routes.py        HTTP-эндпоинты
```

## Эндпоинты (фаза 1.1)

- `GET  /api/health`        — проверка что сервер жив
- `GET  /api/jira/check`    — проверка Jira-доступа
- `POST /api/sprint/build`  — собрать кандидатов и распределить по людям
