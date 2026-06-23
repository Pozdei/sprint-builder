"""Репозиторий спринтов — фильтрация по config_id (фаза 2.7b)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models


def _eager() -> list:
    return [selectinload(models.Sprint.tasks)]


def list_sprints_for_config(db: Session, config_id: int) -> list[models.Sprint]:
    return list(
        db.scalars(
            select(models.Sprint)
            .where(models.Sprint.config_id == config_id)
            .order_by(models.Sprint.sprint_num.desc(), models.Sprint.id.desc())
        ).all()
    )


def list_all_sprints(db: Session) -> list[models.Sprint]:
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


def get_draft_by_num(db: Session, config_id: int, sprint_num: int) -> models.Sprint | None:
    return db.scalar(
        select(models.Sprint)
        .where(
            models.Sprint.config_id == config_id,
            models.Sprint.sprint_num == sprint_num,
            models.Sprint.status == "draft",
        )
        .options(*_eager())
    )


def get_max_approved_num(db: Session, config_id: int) -> int | None:
    return db.scalar(
        select(models.Sprint.sprint_num)
        .where(
            models.Sprint.config_id == config_id,
            models.Sprint.status == "approved",
        )
        .order_by(models.Sprint.sprint_num.desc())
        .limit(1)
    )


def upsert_draft(
    db: Session,
    config_id: int,
    sprint_num: int,
    config_snapshot: dict,
    owner_stats: list[dict],
    tasks: list[dict],
    max_sprint_in_jira: int | None,
) -> models.Sprint:
    existing = get_draft_by_num(db, config_id, sprint_num)

    if existing:
        existing.tasks.clear()
        db.flush()
        existing.config_snapshot = config_snapshot
        existing.owner_stats_snapshot = owner_stats
        existing.max_sprint_in_jira = max_sprint_in_jira
        sprint = existing
    else:
        sprint = models.Sprint(
            config_id=config_id,
            sprint_num=sprint_num,
            status="draft",
            config_snapshot=config_snapshot,
            owner_stats_snapshot=owner_stats,
            max_sprint_in_jira=max_sprint_in_jira,
        )
        db.add(sprint)
        db.flush()

    for i, task in enumerate(tasks, start=1):
        sprint.tasks.append(models.SprintTask(position=i, task_data=task))

    db.commit()
    db.refresh(sprint)
    return sprint


def approve(db: Session, sprint: models.Sprint) -> models.Sprint:
    sprint.status = "approved"
    sprint.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sprint)
    return sprint


def reopen(db: Session, sprint: models.Sprint) -> models.Sprint:
    sprint.status = "draft"
    sprint.approved_at = None
    db.commit()
    db.refresh(sprint)
    return sprint


def delete_sprint(db: Session, sprint: models.Sprint) -> None:
    db.delete(sprint)
    db.commit()


def replace_tasks(db: Session, sprint: models.Sprint,
                   tasks: list[dict], new_owner_stats: list[dict]) -> models.Sprint:
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
                  jira_completed_at,
                  intrusions: list[dict] | None = None) -> models.Sprint:
    for task in sprint.tasks:
        data = closed_data_by_position.get(task.position)
        if data is not None:
            task.closed_task_data = data
    sprint.status = "closed"
    sprint.closed_at = datetime.now(timezone.utc)
    sprint.jira_completed_at = jira_completed_at
    if intrusions is not None:
        sprint.intrusions = intrusions
    db.commit()
    db.refresh(sprint)
    return sprint


# -------------------- Снимки Ганта --------------------

def create_gantt_snapshot(
    db: Session, sprint_id: int, gantt_start: str, hours_per_day: float,
    gantt_items: list[dict], label: str | None = None,
) -> models.SprintGanttSnapshot:
    snap = models.SprintGanttSnapshot(
        sprint_id=sprint_id, gantt_start=gantt_start, hours_per_day=hours_per_day,
        gantt_items=gantt_items, label=label,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def list_gantt_snapshots(db: Session, sprint_id: int) -> list[models.SprintGanttSnapshot]:
    return list(db.scalars(
        select(models.SprintGanttSnapshot)
        .where(models.SprintGanttSnapshot.sprint_id == sprint_id)
        .order_by(models.SprintGanttSnapshot.captured_at.desc())
    ).all())


def get_gantt_snapshot(
    db: Session, sprint_id: int, snapshot_id: int,
) -> models.SprintGanttSnapshot | None:
    return db.scalar(
        select(models.SprintGanttSnapshot)
        .where(
            models.SprintGanttSnapshot.id == snapshot_id,
            models.SprintGanttSnapshot.sprint_id == sprint_id,
        )
    )


def delete_gantt_snapshot(db: Session, sprint_id: int, snapshot_id: int) -> bool:
    snap = get_gantt_snapshot(db, sprint_id, snapshot_id)
    if not snap:
        return False
    db.delete(snap)
    db.commit()
    return True
