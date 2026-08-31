"""Roadmap: горизонтальная шкала по эпикам или по ручной «Детализации»."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import current_config, get_jira_client
from app.core.i18n import get_lang
from app.db import models, repository
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.roadmap import (
    EpicPlanIn, EpicPlanOut, RoadmapGroupOut, RoadmapResponse, RoadmapTaskOut,
    TaskDetailIn, TaskDetailOut,
)
from app.sprint.config import from_dict
from app.sprint.roadmap import build_roadmap_groups, fetch_roadmap_tasks

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.get("", response_model=RoadmapResponse, dependencies=[Depends(get_jira_client)])
def get_roadmap(
    group_by: str = Query("epic", pattern="^(epic|detail)$"),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    """Задачи со всех досок конфига + группировка в разрезе эпика или темы.

    Даты считаются из истории статусов Jira на каждый запрос (кешируется
    только внутри запроса) — на конфигах с большим числом задач построение
    может занять до минуты.
    """
    cfg_dict = repository.model_to_sprint_config_dict(config)
    cfg = from_dict(cfg_dict)

    try:
        rows = fetch_roadmap_tasks(client, cfg)
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))

    details = {d.task_key: d.detail for d in repository.list_task_details(db, config.id)}
    plans = {
        p.epic_key: (p.planned_start, p.planned_end)
        for p in repository.list_epic_plans(db, config.id)
    }
    groups = build_roadmap_groups(rows, group_by, details, plans)

    base_url = client.base_url
    tasks = [
        RoadmapTaskOut(
            key=r["key"], summary=r["summary"], issuetype=r["issuetype"],
            boards=r["boards"], start=r["start"], end=r["end"],
            epic_key=r["epic_key"], epic_summary=r["epic_summary"],
            detail=details.get(r["key"]),
            url=f"{base_url}/browse/{r['key']}",
        )
        for r in rows
    ]

    return RoadmapResponse(
        group_by=group_by,
        groups=[RoadmapGroupOut(**g) for g in groups],
        tasks=tasks,
    )


@router.get("/task-details", response_model=list[TaskDetailOut])
def get_task_details(
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return [
        TaskDetailOut(task_key=d.task_key, detail=d.detail)
        for d in repository.list_task_details(db, config.id)
    ]


@router.put("/task-details", response_model=TaskDetailOut | None)
def put_task_detail(
    body: TaskDetailIn,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    result = repository.set_task_detail(db, config.id, body.task_key, body.detail)
    db.commit()
    return TaskDetailOut(task_key=body.task_key, detail=result.detail) if result else None


@router.get("/epic-plans", response_model=list[EpicPlanOut])
def get_epic_plans(
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return [
        EpicPlanOut(epic_key=p.epic_key, planned_start=p.planned_start, planned_end=p.planned_end)
        for p in repository.list_epic_plans(db, config.id)
    ]


@router.put("/epic-plans", response_model=EpicPlanOut | None)
def put_epic_plan(
    body: EpicPlanIn,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    result = repository.set_epic_plan(db, config.id, body.epic_key, body.planned_start, body.planned_end)
    db.commit()
    return (
        EpicPlanOut(epic_key=body.epic_key, planned_start=result.planned_start, planned_end=result.planned_end)
        if result else None
    )
