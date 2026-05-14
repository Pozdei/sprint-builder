"""Репозиторий конфига: CRUD-операции через SQLAlchemy.

Фаза 2: добавлены roles, role_status_buckets, role_status_default_hours, pseudo_tasks.
Убраны bucket_hours_field и strict_assignee_buckets.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models


_eager_config = [
    selectinload(models.Config.team_members).selectinload(models.TeamMember.pseudo_tasks),
    selectinload(models.Config.boards),
    selectinload(models.Config.components),
    selectinload(models.Config.status_priorities),
    selectinload(models.Config.role_hours_fields),
    selectinload(models.Config.roles),
    selectinload(models.Config.role_status_buckets),
    selectinload(models.Config.role_status_default_hours),
    selectinload(models.Config.pseudo_tasks),
    selectinload(models.Config.terminal_statuses),
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


# -------------------- Перезапись коллекций (с flush между clear и insert) --------------------

def upsert_team_members(db: Session, config: models.Config, items: list[dict]) -> None:
    """items: список dict с jira_account_id, jira_name, file_name, role, sort_order."""
    config.team_members.clear()
    db.flush()
    for i, item in enumerate(items):
        config.team_members.append(
            models.TeamMember(
                jira_account_id=item["jira_account_id"],
                jira_name=item["jira_name"],
                file_name=item["file_name"],
                role=item.get("role", "analyst"),
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


def upsert_status_priorities(db: Session, config: models.Config,
                              items: dict[str, int]) -> None:
    config.status_priorities.clear()
    db.flush()
    for status, prio in items.items():
        config.status_priorities.append(
            models.StatusPriority(jira_status=status, priority=prio)
        )


def upsert_role_hours_fields(db: Session, config: models.Config,
                              items: dict[str, str]) -> None:
    config.role_hours_fields.clear()
    db.flush()
    for role, fid in items.items():
        config.role_hours_fields.append(
            models.RoleHoursField(role=role, customfield_id=fid)
        )


def upsert_roles(db: Session, config: models.Config, items: list[dict]) -> None:
    """items: список dict с name, display_name, enabled, is_lead, sort_order."""
    config.roles.clear()
    db.flush()
    for i, item in enumerate(items):
        config.roles.append(
            models.Role(
                name=item["name"],
                display_name=item["display_name"],
                enabled=item.get("enabled", True),
                is_lead=item.get("is_lead", False),
                sort_order=item.get("sort_order", i),
            )
        )


def upsert_role_status_buckets(db: Session, config: models.Config,
                                items: list[dict]) -> None:
    """items: список dict с role, jira_status, bucket."""
    config.role_status_buckets.clear()
    db.flush()
    for item in items:
        config.role_status_buckets.append(
            models.RoleStatusBucket(
                role=item["role"],
                jira_status=item["jira_status"],
                bucket=item["bucket"],
            )
        )


def upsert_role_status_default_hours(db: Session, config: models.Config,
                                      items: list[dict]) -> None:
    """items: список dict с role, jira_status, hours."""
    config.role_status_default_hours.clear()
    db.flush()
    for item in items:
        config.role_status_default_hours.append(
            models.RoleStatusDefaultHours(
                role=item["role"],
                jira_status=item["jira_status"],
                hours=item["hours"],
            )
        )


def upsert_pseudo_tasks(db: Session, config: models.Config,
                        items: list[dict]) -> None:
    """items: список dict с member_id, name, bucket, hours, recurring, target_sprint_num.

    Внимание: member_id должен соответствовать реальным id из team_members
    в этом конфиге. Если пришёл несуществующий — будет ошибка FK.
    """
    config.pseudo_tasks.clear()
    db.flush()
    for item in items:
        config.pseudo_tasks.append(
            models.PseudoTask(
                member_id=item["member_id"],
                name=item["name"],
                bucket=item["bucket"],
                hours=item["hours"],
                recurring=item.get("recurring", False),
                target_sprint_num=item.get("target_sprint_num"),
            )
        )


def upsert_terminal_statuses(db: Session, config: models.Config,
                              items: list[str]) -> None:
    """Заменить список терминальных статусов."""
    config.terminal_statuses.clear()
    db.flush()
    for i, status in enumerate(items):
        config.terminal_statuses.append(
            models.TerminalStatus(jira_status=status, sort_order=i)
        )


# -------------------- Обновление конфига --------------------

def update_config(db: Session, config_id: int, data: dict) -> models.Config | None:
    config = get_config(db, config_id)
    if not config:
        return None

    for field in ("name", "project_key", "sprint_field", "responsible_field",
                  "hours_per_person", "default_task_hours",
                  "leader_hours", "leader_management_enabled"):
        if field in data:
            setattr(config, field, data[field])

    if "team" in data:
        # team — dict {accountId: {jira_name, file_name, role}}
        items = [
            {
                "jira_account_id": acc_id,
                "jira_name": info["jira_name"],
                "file_name": info["file_name"],
                "role": info.get("role", "analyst"),
            }
            for acc_id, info in data["team"].items()
        ]
        upsert_team_members(db, config, items)

    if "boards" in data:
        upsert_boards(db, config, [
            {"name": name, "jira_board_id": bid}
            for name, bid in data["boards"].items()
        ])
    if "extra_components" in data:
        upsert_components(db, config, data["extra_components"])
    if "status_priority" in data:
        upsert_status_priorities(db, config, data["status_priority"])
    if "role_hours_fields" in data:
        upsert_role_hours_fields(db, config, data["role_hours_fields"])

    if "roles" in data:
        upsert_roles(db, config, data["roles"])
    if "role_status_buckets" in data:
        upsert_role_status_buckets(db, config, data["role_status_buckets"])
    if "role_status_default_hours" in data:
        upsert_role_status_default_hours(db, config, data["role_status_default_hours"])
    if "pseudo_tasks" in data:
        upsert_pseudo_tasks(db, config, data["pseudo_tasks"])
    if "terminal_statuses" in data:
        upsert_terminal_statuses(db, config, data["terminal_statuses"])

    db.commit()
    db.refresh(config)
    return config


# -------------------- Преобразование в dict для бизнес-логики --------------------

def model_to_sprint_config_dict(config: models.Config) -> dict:
    """ORM → dict в формате, ожидаемом сервисами и бизнес-логикой.

    Структура расширена под фазу 2: вместо плоских team/status_bucket теперь
    включает roles, role_status_buckets, role_status_default_hours, pseudo_tasks.
    """
    return {
        "project_key": config.project_key,
        "sprint_field": config.sprint_field,
        "responsible_field": config.responsible_field,
        "hours_per_person": config.hours_per_person,
        "default_task_hours": config.default_task_hours,
        "leader_hours": config.leader_hours,
        "leader_management_enabled": config.leader_management_enabled,
        "team": {
            tm.jira_account_id: {
                "jira_name": tm.jira_name,
                "file_name": tm.file_name,
                "role": tm.role,
                "id": tm.id,  # нужно для привязки pseudo_tasks
            }
            for tm in sorted(config.team_members, key=lambda m: m.sort_order)
        },
        "boards": {b.name: b.jira_board_id for b in config.boards},
        "extra_components": [c.name for c in config.components],
        "status_priority": {sp.jira_status: sp.priority for sp in config.status_priorities},
        "role_hours_fields": {rh.role: rh.customfield_id for rh in config.role_hours_fields},
        "roles": [
            {
                "name": r.name,
                "display_name": r.display_name,
                "enabled": r.enabled,
                "is_lead": r.is_lead,
                "sort_order": r.sort_order,
            }
            for r in sorted(config.roles, key=lambda x: x.sort_order)
        ],
        "role_status_buckets": [
            {"role": rsb.role, "jira_status": rsb.jira_status, "bucket": rsb.bucket}
            for rsb in config.role_status_buckets
        ],
        "role_status_default_hours": [
            {"role": rsdh.role, "jira_status": rsdh.jira_status, "hours": rsdh.hours}
            for rsdh in config.role_status_default_hours
        ],
        "pseudo_tasks": [
            {
                "member_id": pt.member_id,
                "name": pt.name,
                "bucket": pt.bucket,
                "hours": pt.hours,
                "recurring": pt.recurring,
                "target_sprint_num": pt.target_sprint_num,
            }
            for pt in config.pseudo_tasks
        ],
        "terminal_statuses": [
            ts.jira_status
            for ts in sorted(config.terminal_statuses, key=lambda x: x.sort_order)
        ],
    }
