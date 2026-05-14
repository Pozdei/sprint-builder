"""Config service — операции с конфигом."""

from sqlalchemy.orm import Session

from app.db import models, repository


def list_configs(db: Session) -> list[models.Config]:
    return repository.list_configs(db)


def get_default(db: Session) -> models.Config | None:
    return repository.get_default_config(db)


def get_by_id(db: Session, config_id: int) -> models.Config | None:
    return repository.get_config(db, config_id)


def update(db: Session, config_id: int, data: dict) -> models.Config | None:
    return repository.update_config(db, config_id, data)


def to_out_dict(config: models.Config) -> dict:
    """ORM → dict под Pydantic-схему ConfigOut.

    team в ConfigOut — это {accountId: TeamMemberOut}, где TeamMemberOut содержит
    id (нужен для привязки pseudo_tasks).
    """
    base = repository.model_to_sprint_config_dict(config)

    return {
        "id": config.id,
        "name": config.name,
        "is_default": config.is_default,
        "project_key": base["project_key"],
        "sprint_field": base["sprint_field"],
        "responsible_field": base["responsible_field"],
        "hours_per_person": base["hours_per_person"],
        "default_task_hours": base["default_task_hours"],
        "leader_hours": base["leader_hours"],
        "leader_management_enabled": base["leader_management_enabled"],
        "team": base["team"],  # уже включает id, jira_name, file_name, role
        "boards": base["boards"],
        "extra_components": base["extra_components"],
        "status_priority": base["status_priority"],
        "role_hours_fields": base["role_hours_fields"],
        "roles": base["roles"],
        "role_status_buckets": base["role_status_buckets"],
        "role_status_default_hours": base["role_status_default_hours"],
        "pseudo_tasks": base["pseudo_tasks"],
        "terminal_statuses": base.get("terminal_statuses", []),
    }
