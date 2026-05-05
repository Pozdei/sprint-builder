"""Репозиторий конфига: CRUD-операции через SQLAlchemy.

Эндпоинты работают только с этим модулем, не с моделями напрямую.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models


# Загружаем конфиг со ВСЕМИ дочерними таблицами одним запросом.
_eager_config = [
    selectinload(models.Config.team_members),
    selectinload(models.Config.boards),
    selectinload(models.Config.components),
    selectinload(models.Config.status_buckets),
    selectinload(models.Config.status_priorities),
    selectinload(models.Config.bucket_hours_fields),
    selectinload(models.Config.role_hours_fields),
    selectinload(models.Config.strict_assignee_buckets),
]


def list_configs(db: Session) -> list[models.Config]:
    return list(db.scalars(select(models.Config).options(*_eager_config)).all())


def get_config(db: Session, config_id: int) -> models.Config | None:
    return db.scalar(
        select(models.Config).where(models.Config.id == config_id).options(*_eager_config)
    )


def get_default_config(db: Session) -> models.Config | None:
    return db.scalar(
        select(models.Config).where(models.Config.is_default == True).options(*_eager_config)  # noqa: E712
    )


# -------------------- Перезапись связанных коллекций --------------------
#
# Из-за unique-индексов вида (config_id, bucket) нельзя просто .clear() и .append() —
# SQLAlchemy сначала пытается INSERT новые, и они конфликтуют со старыми.
# Поэтому везде явный flush() между удалением и вставкой:
#   1) clear()  — пометили старые на удаление
#   2) flush()  — выдали DELETE в БД
#   3) append() новых — будут INSERT-ы при следующем flush/commit
#
# Без этого flush() порядок DELETE/INSERT не гарантирован.

def upsert_team_members(db: Session, config: models.Config, items: list[dict]) -> None:
    config.team_members.clear()
    db.flush()
    for i, item in enumerate(items):
        config.team_members.append(
            models.TeamMember(
                jira_account_id=item["jira_account_id"],
                jira_name=item["jira_name"],
                file_name=item["file_name"],
                sort_order=item.get("sort_order", i),
            )
        )


def upsert_boards(db: Session, config: models.Config, items: list[dict]) -> None:
    config.boards.clear()
    db.flush()
    for item in items:
        config.boards.append(
            models.ConfigBoard(name=item["name"], jira_board_id=item["jira_board_id"])
        )


def upsert_components(db: Session, config: models.Config, items: list[str]) -> None:
    config.components.clear()
    db.flush()
    for name in items:
        config.components.append(models.ConfigComponent(name=name))


def upsert_status_buckets(db: Session, config: models.Config, items: dict[str, str]) -> None:
    config.status_buckets.clear()
    db.flush()
    for status, bucket in items.items():
        config.status_buckets.append(models.StatusBucket(jira_status=status, bucket=bucket))


def upsert_status_priorities(db: Session, config: models.Config, items: dict[str, int]) -> None:
    config.status_priorities.clear()
    db.flush()
    for status, prio in items.items():
        config.status_priorities.append(models.StatusPriority(jira_status=status, priority=prio))


def upsert_bucket_hours_fields(db: Session, config: models.Config, items: dict[str, str]) -> None:
    config.bucket_hours_fields.clear()
    db.flush()
    for bucket, fid in items.items():
        config.bucket_hours_fields.append(
            models.BucketHoursField(bucket=bucket, customfield_id=fid)
        )


def upsert_role_hours_fields(db: Session, config: models.Config, items: dict[str, str]) -> None:
    config.role_hours_fields.clear()
    db.flush()
    for role, fid in items.items():
        config.role_hours_fields.append(
            models.RoleHoursField(role=role, customfield_id=fid)
        )


def upsert_strict_assignee_buckets(db: Session, config: models.Config, items: list[str]) -> None:
    config.strict_assignee_buckets.clear()
    db.flush()
    for bucket in items:
        config.strict_assignee_buckets.append(models.StrictAssigneeBucket(bucket=bucket))


def update_config(db: Session, config_id: int, data: dict) -> models.Config | None:
    """Полное обновление конфига одним вызовом."""
    config = get_config(db, config_id)
    if not config:
        return None

    if "name" in data:
        config.name = data["name"]
    if "project_key" in data:
        config.project_key = data["project_key"]
    if "sprint_field" in data:
        config.sprint_field = data["sprint_field"]
    if "responsible_field" in data:
        config.responsible_field = data["responsible_field"]
    if "hours_per_person" in data:
        config.hours_per_person = data["hours_per_person"]
    if "default_task_hours" in data:
        config.default_task_hours = data["default_task_hours"]

    if "team" in data:
        items = [
            {
                "jira_account_id": acc_id,
                "jira_name": info["jira_name"],
                "file_name": info["file_name"],
            }
            for acc_id, info in data["team"].items()
        ]
        upsert_team_members(db, config, items)

    if "boards" in data:
        upsert_boards(db, config, [
            {"name": name, "jira_board_id": board_id}
            for name, board_id in data["boards"].items()
        ])

    if "extra_components" in data:
        upsert_components(db, config, data["extra_components"])
    if "status_bucket" in data:
        upsert_status_buckets(db, config, data["status_bucket"])
    if "status_priority" in data:
        upsert_status_priorities(db, config, data["status_priority"])
    if "bucket_hours_field" in data:
        upsert_bucket_hours_fields(db, config, data["bucket_hours_field"])
    if "role_hours_fields" in data:
        upsert_role_hours_fields(db, config, data["role_hours_fields"])
    if "strict_assignee_buckets" in data:
        upsert_strict_assignee_buckets(db, config, list(data["strict_assignee_buckets"]))

    db.commit()
    db.refresh(config)
    return config


def model_to_sprint_config_dict(config: models.Config) -> dict:
    """Преобразовать ORM-объект в dict в формате SprintConfig."""
    return {
        "project_key": config.project_key,
        "sprint_field": config.sprint_field,
        "responsible_field": config.responsible_field,
        "hours_per_person": config.hours_per_person,
        "default_task_hours": config.default_task_hours,
        "team": {
            tm.jira_account_id: {"jira_name": tm.jira_name, "file_name": tm.file_name}
            for tm in sorted(config.team_members, key=lambda m: m.sort_order)
        },
        "boards": {b.name: b.jira_board_id for b in config.boards},
        "extra_components": [c.name for c in config.components],
        "status_bucket": {sb.jira_status: sb.bucket for sb in config.status_buckets},
        "status_priority": {sp.jira_status: sp.priority for sp in config.status_priorities},
        "bucket_hours_field": {bh.bucket: bh.customfield_id for bh in config.bucket_hours_fields},
        "role_hours_fields": {rh.role: rh.customfield_id for rh in config.role_hours_fields},
        "strict_assignee_buckets": {sab.bucket for sab in config.strict_assignee_buckets},
    }
