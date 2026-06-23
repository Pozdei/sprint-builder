"""Схемы для Гант-диаграммы и стендапа."""

from pydantic import BaseModel


class TaskDependency(BaseModel):
    from_key: str
    to_key: str


class RootTaskOut(BaseModel):
    owner_id: str
    task_key: str


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
    is_historical: bool = False   # True — реконструированная фаза из истории Jira
    phase_status: str | None = None  # статус Jira, в котором задача была в эту фазу
    phase_cost: float = 0.0  # стоимость этапа по окладу исполнителя
    parent_key: str | None = None     # непосредственный родитель (свод «Консолидировано»)
    parent_summary: str | None = None
    story_key: str | None = None      # предок типа «История» (свод по User Story)
    story_summary: str | None = None
    epic_key: str | None = None       # предок типа «Эпик» (свод по эпикам)
    epic_summary: str | None = None


class GanttSnapshotSummary(BaseModel):
    id: int
    captured_at: str   # ISO datetime
    label: str | None = None
    gantt_start: str
    hours_per_day: float


class GanttSnapshotDetail(GanttSnapshotSummary):
    gantt_items: list[GanttItem]


class GanttSnapshotCreate(BaseModel):
    gantt_start: str
    hours_per_day: float
    gantt_items: list[GanttItem]
    label: str | None = None


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
