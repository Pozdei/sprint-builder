"""Репозиторий спринтов — CRUD над таблицами sprints и sprint_tasks."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models


def _eager() -> list:
    return [selectinload(models.Sprint.tasks)]


def list_sprints(db: Session) -> list[models.Sprint]:
    """Все спринты — последние сверху."""
    return list(
        db.scalars(
            select(models.Sprint)
            .order_by(models.Sprint.sprint_num.desc(), models.Sprint.id.desc())
        ).all()
    )


def get_sprint(db: Session, sprint_id: int) -> models.Sprint | None:
    return db.scalar(
        select(models.Sprint)
        .where(models.Sprint.id == sprint_id)
        .options(*_eager())
    )


def get_draft_by_num(db: Session, sprint_num: int) -> models.Sprint | None:
    """Draft с указанным номером (если есть)."""
    return db.scalar(
        select(models.Sprint)
        .where(
            models.Sprint.sprint_num == sprint_num,
            models.Sprint.status == "draft",
        )
        .options(*_eager())
    )


def get_max_approved_num(db: Session) -> int | None:
    """Максимальный номер approved-спринта в БД, или None."""
    return db.scalar(
        select(models.Sprint.sprint_num)
        .where(models.Sprint.status == "approved")
        .order_by(models.Sprint.sprint_num.desc())
        .limit(1)
    )


def upsert_draft(
    db: Session,
    sprint_num: int,
    config_snapshot: dict,
    owner_stats: list[dict],
    tasks: list[dict],
    max_sprint_in_jira: int | None,
) -> models.Sprint:
    """Создать draft с указанным номером, или перезаписать существующий.

    Если есть approved с таким же номером — это ОШИБКА вызывающего кода
    (сервис должен был не пустить эту ситуацию). Здесь не проверяем.
    """
    existing = get_draft_by_num(db, sprint_num)

    if existing:
        # Перезапись — очищаем задачи, переставляем поля
        existing.tasks.clear()
        db.flush()  # как в репозитории конфига — иначе INSERT новых упрётся в FK
        existing.config_snapshot = config_snapshot
        existing.owner_stats_snapshot = owner_stats
        existing.max_sprint_in_jira = max_sprint_in_jira
        # created_at не трогаем — это всё ещё тот же draft, просто перезаполненный
        sprint = existing
    else:
        sprint = models.Sprint(
            sprint_num=sprint_num,
            status="draft",
            config_snapshot=config_snapshot,
            owner_stats_snapshot=owner_stats,
            max_sprint_in_jira=max_sprint_in_jira,
        )
        db.add(sprint)
        db.flush()  # получим sprint.id

    for i, task in enumerate(tasks, start=1):
        sprint.tasks.append(models.SprintTask(position=i, task_data=task))

    db.commit()
    db.refresh(sprint)
    return sprint


def approve(db: Session, sprint: models.Sprint) -> models.Sprint:
    """Перевести draft в approved. Время — текущее UTC."""
    sprint.status = "approved"
    sprint.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sprint)
    return sprint


def delete_sprint(db: Session, sprint: models.Sprint) -> None:
    db.delete(sprint)
    db.commit()


def replace_tasks(db: Session, sprint: models.Sprint,
                   tasks: list[dict], new_owner_stats: list[dict]) -> models.Sprint:
    """Полностью заменить sprint_tasks и обновить owner_stats_snapshot.

    Используется для ручного редактирования draft через UI.
    """
    sprint.tasks.clear()
    db.flush()
    for i, t in enumerate(tasks, start=1):
        sprint.tasks.append(models.SprintTask(position=i, task_data=t))
    sprint.owner_stats_snapshot = new_owner_stats
    db.commit()
    db.refresh(sprint)
    return sprint


def close_sprint(db: Session, sprint: models.Sprint,
                  closed_data_by_position: dict[int, dict],
                  jira_completed_at) -> models.Sprint:
    """Закрыть спринт: сохранить снапшот статусов и перевести в closed."""
    from datetime import datetime, timezone as tz
    for task in sprint.tasks:
        data = closed_data_by_position.get(task.position)
        if data is not None:
            task.closed_task_data = data
    sprint.status = "closed"
    sprint.closed_at = datetime.now(tz.utc)
    sprint.jira_completed_at = jira_completed_at
    db.commit()
    db.refresh(sprint)
    return sprint
