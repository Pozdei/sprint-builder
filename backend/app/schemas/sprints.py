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
    """Снапшот состояния задачи в Jira на момент закрытия спринта."""
    status_name: str
    fetched_at: str


class SprintTaskOut(BaseModel):
    """Задача спринта с возможным снапшотом закрытия."""
    task: TaskOut
    closed: ClosedTaskData | None = None


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
    # Снапшоты закрытия — в том же порядке, что tasks. None если closed_task_data пуст.
    closed_tasks: list[ClosedTaskData | None] = []


class SaveDraftRequest(BaseModel):
    allocated: list[TaskOut]
    owner_stats: list[OwnerStat]
    max_sprint_in_jira: int | None = None


class SetTasksRequest(BaseModel):
    tasks: list[TaskOut]
