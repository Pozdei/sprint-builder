"""Репозиторий конфига: CRUD-операции через SQLAlchemy.

Фаза 2.8: добавлен Person, team_member ссылается на person_id.
Источник данных о человеке — Person (jira_account_id, jira_name, file_name),
старые поля в team_members оставлены для совместимости и заполняются из Person.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models, people_repository


_eager_config = [
    selectinload(models.Config.team_members)
        .selectinload(models.TeamMember.person),
    selectinload(models.Config.team_members)
        .selectinload(models.TeamMember.pseudo_tasks),
    selectinload(models.Config.boards),
    selectinload(models.Config.components),
    selectinload(models.Config.status_priorities),
    selectinload(models.Config.role_hours_fields),
    selectinload(models.Config.roles),
    selectinload(models.Config.role_status_buckets),
    selectinload(models.Config.role_status_default_hours),
    selectinload(models.Config.pseudo_tasks),
    selectinload(models.Config.terminal_statuses),
    selectinload(models.Config.directions),
]


def list_configs(db: Session) -> list[models.Config]:
    return list(db.scalars(select(models.Config).options(*_eager_config)).all())


def list_configs_for_user(db: Session, owner_user_id: int) -> list[models.Config]:
    return list(db.scalars(
        select(models.Config)
        .where(models.Config.owner_user_id == owner_user_id)
        .order_by(models.Config.id)
        .options(*_eager_config)
    ).all())


def get_config(db: Session, config_id: int) -> models.Config | None:
    return db.scalar(
        select(models.Config).where(models.Config.id == config_id).options(*_eager_config)
    )


def get_user_config_by_name(db: Session, owner_user_id: int, name: str) -> models.Config | None:
    return db.scalar(
        select(models.Config)
        .where(models.Config.owner_user_id == owner_user_id,
               models.Config.name == name)
        .options(*_eager_config)
    )


# -------------------- Перезапись коллекций --------------------

def upsert_team_members(db: Session, config: models.Config, items: list[dict]) -> None:
    """items: список dict с jira_account_id, jira_name, file_name, role, sort_order.

    Под капотом находим/создаём Person в справочнике пользователя.
    """
    config.team_members.clear()
    db.flush()
    owner_id = config.owner_user_id
    for i, item in enumerate(items):
        person = None
        if owner_id is not None:
            person = people_repository.get_or_create_person(
                db, owner_id,
                jira_account_id=item["jira_account_id"],
                jira_name=item["jira_name"],
                file_name=item["file_name"],
            )
        config.team_members.append(
            models.TeamMember(
                person_id=person.id if person else None,
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


def upsert_directions(db: Session, config: models.Config,
                      items: list[dict]) -> None:
    config.directions.clear()
    db.flush()
    for item in items:
        config.directions.append(
            models.ConfigDirection(
                name=item["name"],
                labels=item.get("labels", []),
                work_types=item.get("work_types", []),
                dev_role=item.get("dev_role") or None,
                tester_role=item.get("tester_role") or None,
                analyst_role=item.get("analyst_role") or None,
            )
        )


def upsert_terminal_statuses(db: Session, config: models.Config,
                              items: list[str]) -> None:
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
                  "leader_hours", "leader_management_enabled", "developer_field"):
        if field in data:
            setattr(config, field, data[field])

    if "team" in data:
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
    if "directions" in data:
        upsert_directions(db, config, data["directions"])

    db.commit()
    db.refresh(config)
    return config


# -------------------- Преобразование в dict --------------------

def model_to_sprint_config_dict(config: models.Config) -> dict:
    """ORM → dict в формате, ожидаемом сервисами и бизнес-логикой.

    Источник правды о человеке — Person (если есть). Если person_id NULL —
    fallback на старые поля в team_member.
    """
    team: dict = {}
    for tm in sorted(config.team_members, key=lambda m: m.sort_order):
        if tm.person is not None:
            acc_id = tm.person.jira_account_id
            jira_name = tm.person.jira_name
            file_name = tm.person.file_name
        else:
            acc_id = tm.jira_account_id
            jira_name = tm.jira_name
            file_name = tm.file_name
        team[acc_id] = {
            "jira_name": jira_name,
            "file_name": file_name,
            "role": tm.role,
            "id": tm.id,
            "person_id": tm.person_id,
        }

    return {
        "project_key": config.project_key,
        "sprint_field": config.sprint_field,
        "responsible_field": config.responsible_field,
        "hours_per_person": config.hours_per_person,
        "default_task_hours": config.default_task_hours,
        "leader_hours": config.leader_hours,
        "leader_management_enabled": config.leader_management_enabled,
        "developer_field": config.developer_field or "",
        "team": team,
        "boards": {b.name: b.jira_board_id for b in config.boards},
        "extra_components": [c.name for c in config.components],
        "status_priority": {sp.jira_status: sp.priority for sp in config.status_priorities},
        "role_hours_fields": {rh.role: rh.customfield_id for rh in config.role_hours_fields},
        "roles": [
            {
                "name": r.name, "display_name": r.display_name,
                "enabled": r.enabled, "is_lead": r.is_lead,
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
        "directions": [
            {
                "name": d.name,
                "labels": d.labels,
                "work_types": d.work_types,
                "dev_role":     d.dev_role or "",
                "tester_role":  d.tester_role or "",
                "analyst_role": d.analyst_role or "",
            }
            for d in config.directions
        ],
    }
