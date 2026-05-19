"""Сервис аутентификации."""

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db import models, users_repository


class AuthError(Exception):
    """Ошибка аутентификации (плохие creds, заблокирован)."""


def authenticate(db: Session, email: str, password: str) -> tuple[models.User, str]:
    """Проверить логин/пароль, вернуть (user, jwt_token).

    Поднимает AuthError при неверных creds или неактивном пользователе.
    """
    user = users_repository.get_user_by_email(db, email)
    if not user:
        raise AuthError("Неверный email или пароль")
    if not user.is_active:
        raise AuthError("Пользователь деактивирован")
    if not verify_password(password, user.password_hash):
        raise AuthError("Неверный email или пароль")

    token = create_access_token(user.id, user.role)
    return user, token


def ensure_admin_exists(db: Session, email: str, password: str) -> None:
    """Создать первого админа из settings, если в БД нет ни одного админа.

    Идемпотентно — если админ уже есть, ничего не делает.
    """
    from sqlalchemy import select
    existing = db.scalar(select(models.User).where(models.User.role == "admin"))
    if existing:
        return
    users_repository.create_user(
        db,
        email=email,
        password_hash=hash_password(password),
        role="admin",
        display_name="Администратор",
    )
    print(f"[seed] Создан первый администратор: {email}")
