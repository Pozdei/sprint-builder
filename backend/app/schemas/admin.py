"""Схемы для админских эндпоинтов."""

from pydantic import BaseModel


class AdminConfigSummary(BaseModel):
    id: int
    name: str
    owner_user_id: int | None
    owner_email: str | None
    owner_display_name: str | None
    sprints_count: int


class AdminSprintSummary(BaseModel):
    id: int
    sprint_num: int
    status: str
    config_id: int | None
    owner_email: str | None
