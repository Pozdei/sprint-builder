"""Сервис админских операций над пользователями.

Защиты:
- Нельзя удалить себя.
- Нельзя удалить или деактивировать последнего активного админа.
- Нельзя сменить роль с admin на lead для последнего активного админа.
- Передача конфига возможна только lead-пользователю.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db import models, users_repository


class AdminActionError(Exception):
    """Ошибка админской операции (валидация, защитные правила)."""


_VALID_ROLES = {"admin", "lead"}


def _count_active_admins(db: Session, exclude_user_id: int | None = None) -> int:
    q = select(models.User).where(
        models.User.role == "admin",
        models.User.is_active == True,  # noqa: E712
    )
    if exclude_user_id is not None:
        q = q.where(models.User.id != exclude_user_id)
    return len(db.scalars(q).all())


def create_user(db: Session, *, email: str, password: str, role: str,
                 display_name: str = "") -> models.User:
    if role not in _VALID_ROLES:
        raise AdminActionError(f"Неизвестная роль: {role!r}")
    if users_repository.get_user_by_email(db, email):
        raise AdminActionError(f"Пользователь {email} уже существует")
    return users_repository.create_user(
        db,
        email=email,
        password_hash=hash_password(password),
        role=role,
        display_name=display_name,
    )


def update_user(db: Session, *, target: models.User,
                 display_name: str | None = None,
                 role: str | None = None,
                 is_active: bool | None = None) -> models.User:
    """Обновить поля пользователя с защитой последнего админа."""
    if role is not None and role not in _VALID_ROLES:
        raise AdminActionError(f"Неизвестная роль: {role!r}")

    target_is_active_admin = target.role == "admin" and target.is_active
    new_role = role if role is not None else target.role
    new_active = is_active if is_active is not None else target.is_active
    will_be_active_admin = new_role == "admin" and new_active

    if target_is_active_admin and not will_be_active_admin:
        if _count_active_admins(db, exclude_user_id=target.id) == 0:
            raise AdminActionError(
                "Это последний активный администратор. Сначала создай другого."
            )

    fields: dict = {}
    if display_name is not None:
        fields["display_name"] = display_name
    if role is not None:
        fields["role"] = role
    if is_active is not None:
        fields["is_active"] = is_active

    if not fields:
        return target

    return users_repository.update_user(db, target, **fields)


def reset_password(db: Session, target: models.User, new_password: str) -> None:
    if not new_password:
        raise AdminActionError("Пароль не может быть пустым")
    users_repository.update_user(db, target, password_hash=hash_password(new_password))


def delete_user(db: Session, target: models.User, current_admin_id: int) -> None:
    """Удалить пользователя с его конфигом и спринтами (через CASCADE).

    Запрещено: удалить себя, удалить последнего активного админа.
    """
    if target.id == current_admin_id:
        raise AdminActionError("Нельзя удалить самого себя")
    if target.role == "admin" and target.is_active:
        if _count_active_admins(db, exclude_user_id=target.id) == 0:
            raise AdminActionError(
                "Это последний активный администратор. Сначала создай другого."
            )
    users_repository.delete_user(db, target)


def transfer_config(db: Session, config: models.Config,
                     new_owner: models.User) -> models.Config:
    """Передать конфиг другому lead-пользователю.

    У одного пользователя не больше одного конфига. Если у нового владельца
    уже есть свой конфиг — это ошибка: пусть админ сначала удалит/передаст его.
    """
    if new_owner.role != "lead":
        raise AdminActionError(
            "Конфиг можно передать только lead-пользователю. "
            "У админа не должно быть конфига."
        )

    existing = db.scalar(
        select(models.Config).where(models.Config.owner_user_id == new_owner.id)
    )
    if existing and existing.id != config.id:
        raise AdminActionError(
            f"У пользователя {new_owner.email} уже есть конфиг (id={existing.id}). "
            f"Удалите его или передайте другому пользователю сначала."
        )

    config.owner_user_id = new_owner.id
    db.commit()
    db.refresh(config)
    return config
