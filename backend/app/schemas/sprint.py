"""Схемы для эндпоинтов сборки спринта и кандидатов."""

from pydantic import BaseModel

from app.schemas.task import TaskOut


class OwnerStat(BaseModel):
    owner_id: str
    file_name: str
    used_hours: float
    budget: float


class CandidatesResponse(BaseModel):
    candidates: list[TaskOut]
    diagnostics: dict
    max_sprint_num: int | None


class SprintBuildRequest(BaseModel):
    """Опциональное тело: можно передать уже собранных кандидатов,
    чтобы не дёргать Jira повторно. Если пусто — собираем заново.
    """
    candidates: list[TaskOut] | None = None


class SprintBuildResponse(BaseModel):
    allocated: list[TaskOut]
    overflow: list[TaskOut]
    candidates: list[TaskOut]
    owner_stats: list[OwnerStat]
    diagnostics: dict
    max_sprint_num: int | None
