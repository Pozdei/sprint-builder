"""Схемы для Гант-диаграммы и стендапа."""

from pydantic import BaseModel


class TaskDependency(BaseModel):
    from_key: str
    to_key: str


class EmployeeVacationIn(BaseModel):
    jira_account_id: str
    display_name: str
    start_date: str   # "YYYY-MM-DD"
    end_date: str     # "YYYY-MM-DD"


class EmployeeVacationOut(BaseModel):
    id: int
    jira_account_id: str
    display_name: str
    start_date: str
    end_date: str


class GanttItem(BaseModel):
    key: str
    summary: str
    bucket: str
    role: str
    owner_id: str
    owner_file_name: str
    hours: float
    is_pseudo: bool
    url: str
    direction: str | None = None
    start: str        # ISO datetime
    end: str          # ISO datetime
    start_hours: float
    end_hours: float
    hours_is_default: bool = False


class StandupTask(BaseModel):
    key: str
    summary: str
    url: str
    bucket: str
    planned_start: str
    planned_end: str
    planned_hours: float
    is_overdue: bool


class StandupExecutor(BaseModel):
    owner_id: str
    owner_file_name: str
    role: str
    tasks: list[StandupTask]
