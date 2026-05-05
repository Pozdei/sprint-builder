"""Тип SprintConfig — то, что бизнес-логика ожидает на вход.

Раньше тут жили значения по умолчанию. Теперь они в app/db/seed.py,
а конфиг загружается из БД.
"""

from dataclasses import dataclass, field


@dataclass
class SprintConfig:
    project_key: str
    sprint_field: str
    responsible_field: str
    hours_per_person: float
    default_task_hours: float

    team: dict[str, dict[str, str]] = field(default_factory=dict)
    boards: dict[str, int] = field(default_factory=dict)
    extra_components: list[str] = field(default_factory=list)
    status_bucket: dict[str, str] = field(default_factory=dict)
    status_priority: dict[str, int] = field(default_factory=dict)
    bucket_hours_field: dict[str, str] = field(default_factory=dict)
    role_hours_fields: dict[str, str] = field(default_factory=dict)
    strict_assignee_buckets: set[str] = field(default_factory=set)


def from_dict(data: dict) -> SprintConfig:
    """Создать SprintConfig из dict (формат как в репозитории)."""
    return SprintConfig(
        project_key=data["project_key"],
        sprint_field=data["sprint_field"],
        responsible_field=data["responsible_field"],
        hours_per_person=data["hours_per_person"],
        default_task_hours=data["default_task_hours"],
        team=data.get("team", {}),
        boards=data.get("boards", {}),
        extra_components=data.get("extra_components", []),
        status_bucket=data.get("status_bucket", {}),
        status_priority=data.get("status_priority", {}),
        bucket_hours_field=data.get("bucket_hours_field", {}),
        role_hours_fields=data.get("role_hours_fields", {}),
        strict_assignee_buckets=set(data.get("strict_assignee_buckets", [])),
    )
