"""Схемы запросов на экспорт xlsx."""

from pydantic import BaseModel

from app.schemas.sprint import OwnerStat
from app.schemas.sprints import ClosedTaskData, IntrusionRecord
from app.schemas.task import TaskOut


class SprintExportRequest(BaseModel):
    allocated: list[TaskOut]
    owner_stats: list[OwnerStat]
    max_sprint_num: int | None = None
    closed_tasks: list[ClosedTaskData | None] | None = None
    terminal_statuses: list[str] | None = None
    intrusions: list[IntrusionRecord] | None = None


class CandidatesExportRequest(BaseModel):
    candidates: list[TaskOut]
    max_sprint_num: int | None = None
    # "key|role|bucket" для каждой аллоцированной задачи — None если спринт ещё не собран
    allocated_set: list[str] | None = None
