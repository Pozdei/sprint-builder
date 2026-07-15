"""Схемы для AI-среза (Спринт/Прогноз). Фронтенд шлёт уже посчитанный результат
(SprintBuildResponse / EpicForecastResponse) — бэкенд только форматирует его в
промпт и зовёт LLM, не пересчитывает."""

from pydantic import BaseModel

from app.schemas.gantt import GanttItem
from app.schemas.sprint import OwnerStat
from app.schemas.task import TaskOut


class SprintSummaryRequest(BaseModel):
    allocated: list[TaskOut]
    overflow: list[TaskOut] = []
    owner_stats: list[OwnerStat] = []


class ForecastSummaryRequest(BaseModel):
    epic_key: str = ""
    epic_summary: str = ""
    gantt_items: list[GanttItem]
    completion_date: str | None = None
    stats: dict = {}
    warnings: list[str] = []
    missing_assignees: list[dict] = []


class AiSummaryResponse(BaseModel):
    summary: str
    generated_at: str
