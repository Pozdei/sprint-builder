"""Подключение к БД через SQLAlchemy 2.0.

`engine` — пул соединений (один на приложение).
`SessionLocal` — фабрика сессий (одна сессия на запрос).
`get_db` — FastAPI-зависимость: выдаёт сессию, закрывает после ответа.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # перед использованием соединения проверяем что живо
    echo=False,          # True = логировать SQL (полезно для отладки)
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # после commit() объекты остаются доступны
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Зависимость для эндпоинтов: `db: Session = Depends(get_db)`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
