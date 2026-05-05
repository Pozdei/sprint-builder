"""Alembic environment.

Берёт url БД из app.core.config (а не из alembic.ini), импортирует все модели
для autogenerate.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

# Добавляем корень бэкенда в sys.path — иначе Alembic не найдёт пакет 'app'.
# __file__ = .../backend/migrations/env.py → parents[1] = .../backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import engine_from_config, pool

from alembic import context

# Настройка логирования из alembic.ini
if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

# Подгружаем настройки приложения и метаданные моделей
from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.db import models  # noqa: F401, E402  — регистрируем все модели

# Перекрываем sqlalchemy.url из alembic.ini своим из .env
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Генерация SQL-скрипта без подключения к БД."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применение миграций к живой БД."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
