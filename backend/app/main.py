"""FastAPI приложение — точка входа.

Запуск (из папки backend):
    uvicorn app.main:app --reload --port 8000

Перед первым стартом:
    alembic upgrade head
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from app.api import router
from app.api.errors import integrity_error_handler
from app.core.config import settings
from app.db.seed import seed_default_config
from app.db.session import SessionLocal
from app.services.auth_service import ensure_admin_exists
from app import scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = SessionLocal()
    try:
        seed_default_config(db)
    except Exception as e:
        print(f"[seed] Пропущен — БД не готова: {e}")

    try:
        ensure_admin_exists(db, settings.admin_email, settings.admin_password)
    except Exception as e:
        print(f"[seed] Админ не создан: {e}")

    db.close()

    try:
        scheduler.start()
    except Exception as e:
        print(f"[telegram] Планировщик не запущен: {e}")

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Sprint Builder API",
    description="Формирование спринта на основе данных Jira",
    version="0.10.0",
    lifespan=lifespan,
)

# Дружелюбные ошибки целостности
app.add_exception_handler(IntegrityError, integrity_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:5173",
        "http://127.0.0.1:3000", "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Sprint Builder API", "version": "0.10.0", "docs": "/docs"}
