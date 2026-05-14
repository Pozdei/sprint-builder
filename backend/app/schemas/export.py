"""Схемы запросов на экспорт xlsx."""

from pydantic import BaseModel

from app.schemas.sprint import OwnerStat
from app.schemas.sprints import ClosedTaskData
from app.schemas.task import TaskOut


class SprintExportRequest(BaseModel):
    allocated: list[TaskOut]
    owner_stats: list[OwnerStat]
    max_sprint_num: int | None = None
    # Опциональные поля для closed-спринтов
    closed_tasks: list[ClosedTaskData | None] | None = None
    terminal_statuses: list[str] | None = None


class CandidatesExportRequest(BaseModel):
    candidates: list[TaskOut]
    max_sprint_num: int | None = None
