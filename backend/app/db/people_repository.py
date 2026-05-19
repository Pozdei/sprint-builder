"""Репозиторий справочника людей пользователя."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def list_people(db: Session, owner_user_id: int) -> list[models.Person]:
    return list(db.scalars(
        select(models.Person)
        .where(models.Person.owner_user_id == owner_user_id)
        .order_by(models.Person.jira_name)
    ).all())


def get_person(db: Session, person_id: int) -> models.Person | None:
    return db.get(models.Person, person_id)


def get_or_create_person(db: Session, owner_user_id: int, *,
                          jira_account_id: str, jira_name: str,
                          file_name: str) -> models.Person:
    p = db.scalar(
        select(models.Person).where(
            models.Person.owner_user_id == owner_user_id,
            models.Person.jira_account_id == jira_account_id,
        )
    )
    if p:
        # Обновим имена на свежие значения
        p.jira_name = jira_name
        p.file_name = file_name
        db.flush()
        return p

    p = models.Person(
        owner_user_id=owner_user_id,
        jira_account_id=jira_account_id,
        jira_name=jira_name,
        file_name=file_name,
    )
    db.add(p)
    db.flush()
    return p


def delete_person(db: Session, person: models.Person) -> None:
    db.delete(person)
    db.commit()
