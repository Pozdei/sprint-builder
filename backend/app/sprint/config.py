"""Тип SprintConfig — то, что бизнес-логика ожидает на вход.

Фаза 2: расширена ролями. Бизнес-логика (collect_candidates/allocate) пока
смотрит на старые поля (status_bucket, bucket_hours_field) — мы их собираем
из новых таблиц на лету для роли analyst, чтобы оставить совместимость.

В фазе 2.2 переделаем бизнес-логику и это адаптерство уберём.
"""

from dataclasses import dataclass, field


@dataclass
class SprintConfig:
    # Базовые поля
    project_key: str
    sprint_field: str
    responsible_field: str
    hours_per_person: float
    default_task_hours: float
    leader_hours: float = 20.0
    leader_management_enabled: bool = True

    # Команда: {accountId: {jira_name, file_name, role, id}}
    team: dict[str, dict] = field(default_factory=dict)

    boards: dict[str, int] = field(default_factory=dict)
    extra_components: list[str] = field(default_factory=list)
    status_priority: dict[str, int] = field(default_factory=dict)
    role_hours_fields: dict[str, str] = field(default_factory=dict)

    # Новые поля (фаза 2)
    roles: list[dict] = field(default_factory=list)
    role_status_buckets: list[dict] = field(default_factory=list)   # [{role, jira_status, bucket}]
    role_status_default_hours: list[dict] = field(default_factory=list)  # [{role, jira_status, hours}]
    pseudo_tasks: list[dict] = field(default_factory=list)
    # Фаза 2.5: терминальные статусы для подсчёта % выполнения
    terminal_statuses: list[str] = field(default_factory=list)

    # ---- Совместимость с фазой 1 (для старой бизнес-логики) ----
    # Сейчас collect_candidates и allocate работают только для analyst.
    # Здесь мы выставляем status_bucket и bucket_hours_field так, как ожидала
    # старая логика, на основе role_status_buckets для роли analyst.
    status_bucket: dict[str, str] = field(default_factory=dict)
    bucket_hours_field: dict[str, str] = field(default_factory=dict)
    strict_assignee_buckets: set[str] = field(default_factory=set)


def from_dict(data: dict) -> SprintConfig:
    cfg = SprintConfig(
        project_key=data["project_key"],
        sprint_field=data["sprint_field"],
        responsible_field=data["responsible_field"],
        hours_per_person=data["hours_per_person"],
        default_task_hours=data["default_task_hours"],
        leader_hours=data.get("leader_hours", 20.0),
        leader_management_enabled=data.get("leader_management_enabled", True),
        team=data.get("team", {}),
        boards=data.get("boards", {}),
        extra_components=data.get("extra_components", []),
        status_priority=data.get("status_priority", {}),
        role_hours_fields=data.get("role_hours_fields", {}),
        roles=data.get("roles", []),
        role_status_buckets=data.get("role_status_buckets", []),
        role_status_default_hours=data.get("role_status_default_hours", []),
        pseudo_tasks=data.get("pseudo_tasks", []),
        terminal_statuses=data.get("terminal_statuses", []),
    )

    # Совместимость: собрать status_bucket из role_status_buckets для роли analyst
    cfg.status_bucket = {
        item["jira_status"]: item["bucket"]
        for item in cfg.role_status_buckets
        if item["role"] == "analyst"
    }

    # bucket_hours_field — на старой логике это маппинг бакет → customfield.
    # В новой модели это часть role_hours_fields через косвенную связь:
    # бакет 'Анализ' использует поле аналитика, 'Тестирование' — тестировщика.
    # Эту связь мы хардкодим тут для совместимости — в фазе 2.2 уйдёт.
    cfg.bucket_hours_field = {
        "Анализ":       cfg.role_hours_fields.get("analyst", ""),
        "Тестирование": cfg.role_hours_fields.get("tester", ""),
    }

    return cfg
