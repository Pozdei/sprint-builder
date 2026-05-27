"""Схема одной задачи — используется и в sprint, и в export."""

from pydantic import BaseModel


class TaskOut(BaseModel):
    key: str
    url: str
    summary: str
    status_name: str
    bucket: str
    role: str = "analyst"  # фаза 2: какая роль в спринте у этой задачи
    is_pseudo: bool = False  # псевдо-задача (отпуск, руководство и т.п.)
    owner_id: str
    owner_file_name: str
    hours: float
    board: str
    sprint_num: int | None
    sprint_name: str | None
    formal_only: bool
    priority: int | None = None
    partial_from: float | None = None
    hours_analyst: float | None
    hours_tester: float | None
    hours_developer: float | None
    hours_original: float | None
    # Ожидаемый итог спринта по pipeline (вычисляется при сборке спринта)
    sprint_expected_result: str | None = None
    # Поля для pipeline-логики направлений (round-trip через candidates)
    direction: str | None = None
    labels: list[str] = []
    responsible_id: str | None = None
    assignee_id: str | None = None
    reporter_id: str | None = None
    developer_name: str | None = None
    hours_is_default: bool = False
    overflow_reason: str | None = None
    # Привязка дизайнера/тестировщика к задаче (только в нашем сервисе, не в Jira)
    designer_id: str | None = None
    tester_id: str | None = None
