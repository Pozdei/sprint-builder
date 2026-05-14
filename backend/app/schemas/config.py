"""Схемы для эндпоинтов конфига (фаза 2)."""

from pydantic import BaseModel


class ConfigSummary(BaseModel):
    id: int
    name: str
    is_default: bool


class RoleOut(BaseModel):
    name: str
    display_name: str
    enabled: bool
    is_lead: bool
    sort_order: int


class RoleStatusBucketOut(BaseModel):
    role: str
    jira_status: str
    bucket: str


class RoleStatusDefaultHoursOut(BaseModel):
    role: str
    jira_status: str
    hours: float


class PseudoTaskOut(BaseModel):
    member_id: int
    name: str
    bucket: str
    hours: float
    recurring: bool
    target_sprint_num: int | None = None


class TeamMemberOut(BaseModel):
    """Информация о члене команды в ответе ConfigOut."""
    id: int
    jira_name: str
    file_name: str
    role: str


class ConfigOut(BaseModel):
    """Полный конфиг для клиента."""
    id: int
    name: str
    is_default: bool

    project_key: str
    sprint_field: str
    responsible_field: str
    hours_per_person: float
    default_task_hours: float
    leader_hours: float
    leader_management_enabled: bool

    # team приходит как dict {accountId: TeamMemberOut}
    team: dict[str, TeamMemberOut]
    boards: dict[str, int]
    extra_components: list[str]
    status_priority: dict[str, int]
    role_hours_fields: dict[str, str]

    roles: list[RoleOut]
    role_status_buckets: list[RoleStatusBucketOut]
    role_status_default_hours: list[RoleStatusDefaultHoursOut]
    pseudo_tasks: list[PseudoTaskOut]
    terminal_statuses: list[str]


# -------------------- Тело PUT --------------------

class TeamMemberIn(BaseModel):
    jira_name: str
    file_name: str
    role: str


class ConfigUpdate(BaseModel):
    """Все поля опциональные — обновляем только присланные."""
    name: str | None = None
    project_key: str | None = None
    sprint_field: str | None = None
    responsible_field: str | None = None
    hours_per_person: float | None = None
    default_task_hours: float | None = None
    leader_hours: float | None = None
    leader_management_enabled: bool | None = None

    team: dict[str, TeamMemberIn] | None = None
    boards: dict[str, int] | None = None
    extra_components: list[str] | None = None
    status_priority: dict[str, int] | None = None
    role_hours_fields: dict[str, str] | None = None

    roles: list[dict] | None = None
    role_status_buckets: list[dict] | None = None
    role_status_default_hours: list[dict] | None = None
    pseudo_tasks: list[dict] | None = None
    terminal_statuses: list[str] | None = None
