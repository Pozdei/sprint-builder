"""Схемы Roadmap: горизонтальная шкала по эпикам или по ручной «Детализации»."""

from pydantic import BaseModel


class RoadmapTaskOut(BaseModel):
    key: str
    summary: str
    issuetype: str
    boards: list[str]
    start: str            # "YYYY-MM-DD" или "" — не начата
    end: str              # "YYYY-MM-DD" или "" — не завершена
    epic_key: str | None = None
    epic_summary: str | None = None
    detail: str | None = None
    url: str


class RoadmapGroupOut(BaseModel):
    key: str
    label: str
    boards: list[str]
    total: int
    done: int
    in_progress: int
    not_started: int
    start: str
    end: str               # "" — не все задачи завершены, заполнить вручную
    status: str            # "not_started" | "in_progress" | "done"
    planned_start: str = ""  # ручной план (только group_by="epic"), не переопределяет факт
    planned_end: str = ""


class RoadmapResponse(BaseModel):
    group_by: str           # "epic" | "detail"
    groups: list[RoadmapGroupOut]
    tasks: list[RoadmapTaskOut]


class TaskDetailIn(BaseModel):
    task_key: str
    detail: str             # пустая строка — удалить тему у задачи


class TaskDetailOut(BaseModel):
    task_key: str
    detail: str


class EpicPlanIn(BaseModel):
    epic_key: str
    planned_start: str      # пустая строка — не задано
    planned_end: str


class EpicPlanOut(BaseModel):
    epic_key: str
    planned_start: str
    planned_end: str
