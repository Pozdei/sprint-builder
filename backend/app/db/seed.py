"""Seed заглушка для фазы 2.7+.

Конфиги больше не создаются в seed — они привязаны к lead-юзерам и создаются
автоматически через config_service.get_or_create_user_config при первом обращении.

Админ создаётся отдельно — auth_service.ensure_admin_exists в lifespan main.py.

Функция оставлена для обратной совместимости (вызов в main.py не упадёт).
"""

from sqlalchemy.orm import Session


def seed_default_config(db: Session) -> None:
    # Ничего не делаем — фаза 2.7+ не требует дефолтного конфига при старте
    return
