"""Репозиторий пользователей — CRUD + active_config_id."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def get_user_by_id(db: Session, user_id: int) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.id == user_id))


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.email == email))


def list_users(db: Session) -> list[models.User]:
    return list(db.scalars(select(models.User).order_by(models.User.id)).all())


def create_user(db: Session, *, email: str, password_hash: str, role: str,
                 display_name: str = "", is_active: bool = True) -> models.User:
    user = models.User(
        email=email,
        password_hash=password_hash,
        role=role,
        display_name=display_name,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: models.User, **fields) -> models.User:
    for k, v in fields.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def set_active_config(db: Session, user: models.User,
                       config_id: int | None) -> models.User:
    user.active_config_id = config_id
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: models.User) -> None:
    db.delete(user)
    db.commit()
