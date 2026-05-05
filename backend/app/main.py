"""FastAPI приложение — точка входа.

Запуск (из папки backend):
    uvicorn app.main:app --reload --port 8000

Перед первым стартом убедись что миграции накатаны:
    alembic upgrade head

После старта:
    Swagger UI:   http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.seed import seed_default_config
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Старт/стоп-хук. Здесь — проверка БД и seed."""
    # Пытаемся залить дефолтный конфиг. Если БД ещё не существует или
    # миграции не накачены — будет ошибка, но это нормально: разработчик
    # запустит alembic и перезапустит приложение.
    db = SessionLocal()
    try:
        seed_default_config(db)
    except Exception as e:
        print(f"[seed] Пропущен — БД не готова: {e}")
        print("[seed] Выполни: alembic upgrade head, затем перезапусти.")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Sprint Builder API",
    description="Формирование спринта аналитиков на основе данных Jira",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Sprint Builder API", "version": "0.4.0", "docs": "/docs"}
