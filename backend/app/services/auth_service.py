"""Сервис аутентификации."""

from sqlalchemy.orm import Session

from app.core.i18n import DEFAULT_LANG, make_translator
from app.core.security import create_access_token, hash_password, verify_password
from app.db import models, users_repository

_MSG: dict[str, dict[str, str]] = {
    "bad_credentials": {
        "ru": "Неверный email или пароль",
        "en": "Invalid email or password",
    },
    "user_deactivated": {
        "ru": "Пользователь деактивирован",
        "en": "User is deactivated",
    },
}
_t = make_translator(_MSG)


class AuthError(Exception):
    """Ошибка аутентификации (плохие creds, заблокирован).

    `str(e)` — ru-вариант (обратная совместимость), `.text(lang)` — нужная локаль.
    """

    def __init__(self, key: str, **kwargs):
        self._key = key
        self._kwargs = kwargs
        super().__init__(_t(key, DEFAULT_LANG, **kwargs))

    def text(self, lang: str) -> str:
        return _t(self._key, lang, **self._kwargs)


def authenticate(db: Session, email: str, password: str) -> tuple[models.User, str]:
    """Проверить логин/пароль, вернуть (user, jwt_token).

    Поднимает AuthError при неверных creds или неактивном пользователе.
    """
    user = users_repository.get_user_by_email(db, email)
    if not user:
        raise AuthError("bad_credentials")
    if not user.is_active:
        raise AuthError("user_deactivated")
    if not verify_password(password, user.password_hash):
        raise AuthError("bad_credentials")

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
