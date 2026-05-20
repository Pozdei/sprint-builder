"""Схемы для эндпоинтов истории спринтов."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.sprint import OwnerStat
from app.schemas.task import TaskOut


class SprintSummary(BaseModel):
    id: int
    sprint_num: int
    status: Literal["draft", "approved", "closed"]
    created_at: datetime
    approved_at: datetime | None
    closed_at: datetime | None = None
    tasks_count: int


class ClosedTaskData(BaseModel):
    status_name: str
    fetched_at: str


class IntrusionRecord(BaseModel):
    """Задача, появившаяся в Jira-спринте ПОСЛЕ approve. Считаем только тех,
    чей владелец — из team на момент approve."""
    key: str
    summary: str
    status_name: str
    is_done: bool
    owner_id: str
    owner_file_name: str
    owner_jira_name: str
    role: str
    bucket: str
    hours: float
    url: str | None = None


class SprintOut(BaseModel):
    id: int
    sprint_num: int
    status: Literal["draft", "approved", "closed"]
    created_at: datetime
    approved_at: datetime | None
    closed_at: datetime | None = None
    jira_completed_at: datetime | None = None
    max_sprint_in_jira: int | None
    config_snapshot: dict
    owner_stats: list[OwnerStat]
    tasks: list[TaskOut]
    closed_tasks: list[ClosedTaskData | None] = []
    intrusions: list[IntrusionRecord] = []


class SaveDraftRequest(BaseModel):
    allocated: list[TaskOut]
    owner_stats: list[OwnerStat]
    max_sprint_in_jira: int | None = None


class SetTasksRequest(BaseModel):
    tasks: list[TaskOut]
