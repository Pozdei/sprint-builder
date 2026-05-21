"""Эндпоинты истории спринтов (lead-only)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import current_config
from app.db import models, repository, sprints_repository
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.gantt import GanttItem, StandupExecutor, TaskDependency
from app.schemas.sprints import (
    ClosedTaskData, IntrusionRecord, SaveDraftRequest, SetTasksRequest,
    SprintOut, SprintSummary,
)
from app.services import sprints_service
from app.services.sprints_service import (
    JiraSprintNotClosedError, JiraSprintNotFoundError, SprintAccessDeniedError,
    SprintNotADraftError, SprintNotApprovedError,
)
from app.sprint.gantt import compute_gantt_schedule
from app.sprint.standup import build_standup

router = APIRouter(prefix="/sprints", tags=["sprints"])


def _get_sprint_or_404(db: Session, sprint_id: int, config_id: int) -> models.Sprint:
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint or sprint.config_id != config_id:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    return sprint


def _to_summary(sprint: models.Sprint) -> SprintSummary:
    return SprintSummary(
        id=sprint.id,
        sprint_num=sprint.sprint_num,
        status=sprint.status,  # type: ignore[arg-type]
        created_at=sprint.created_at,
        approved_at=sprint.approved_at,
        closed_at=sprint.closed_at,
        tasks_count=len(sprint.tasks) if sprint.tasks is not None else 0,
    )


def _to_out(sprint: models.Sprint) -> SprintOut:
    closed_list = []
    for t in sprint.tasks:
        if t.closed_task_data:
            closed_list.append(ClosedTaskData(
                status_name=t.closed_task_data.get("status_name", ""),
                fetched_at=t.closed_task_data.get("fetched_at", ""),
            ))
        else:
            closed_list.append(None)

    intrusions = []
    for it in (sprint.intrusions or []):
        if not isinstance(it, dict):
            continue
        try:
            intrusions.append(IntrusionRecord(**it))
        except Exception:
            continue

    return SprintOut(
        id=sprint.id,
        sprint_num=sprint.sprint_num,
        status=sprint.status,  # type: ignore[arg-type]
        created_at=sprint.created_at,
        approved_at=sprint.approved_at,
        closed_at=sprint.closed_at,
        jira_completed_at=sprint.jira_completed_at,
        max_sprint_in_jira=sprint.max_sprint_in_jira,
        config_snapshot=sprint.config_snapshot,
        owner_stats=sprint.owner_stats_snapshot,
        tasks=[t.task_data for t in sprint.tasks],
        closed_tasks=closed_list,
        intrusions=intrusions,
    )


@router.get("", response_model=list[SprintSummary])
def list_all(
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return [_to_summary(s) for s in sprints_repository.list_sprints_for_config(db, config.id)]


@router.get("/{sprint_id}", response_model=SprintOut)
def get_one(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return _to_out(_get_sprint_or_404(db, sprint_id, config.id))


@router.post("/draft", response_model=SprintOut)
def save_draft(
    body: SaveDraftRequest,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    try:
        sprint_num = sprints_service.compute_next_sprint_num(
            db, config.id, body.max_sprint_in_jira,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        sprint = sprints_service.save_draft(
            db,
            sprint_num=sprint_num,
            config=config,
            allocated=[t.model_dump() for t in body.allocated],
            owner_stats=[s.model_dump() for s in body.owner_stats],
            max_sprint_in_jira=body.max_sprint_in_jira,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return _to_out(sprint)


@router.post("/{sprint_id}/approve", response_model=SprintOut)
def approve(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    try:
        sprint = sprints_service.approve_sprint(db, client, sprint_id, config.id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    except SprintNotADraftError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except JiraSprintNotFoundError as e:
        raise HTTPException(status_code=412, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return _to_out(sprint)


@router.post("/{sprint_id}/close", response_model=SprintOut)
def close(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    try:
        sprint = sprints_service.close_sprint(db, client, sprint_id, config.id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    except SprintNotApprovedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except JiraSprintNotClosedError as e:
        raise HTTPException(status_code=412, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return _to_out(sprint)


@router.get("/{sprint_id}/standup", response_model=list[StandupExecutor])
def get_standup(
    sprint_id: int,
    sprint_start: date = Query(..., description="Дата начала спринта"),
    standup_date: date = Query(..., description="Дата стендапа (обычно сегодня)"),
    hours_per_day: float = Query(8.0, ge=1, le=24),
    roles: str = Query("", description="Роли через запятую; пусто = все"),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id)

    role_filter: set[str] | None = None
    if roles.strip():
        role_filter = {r.strip() for r in roles.split(",") if r.strip()}

    return build_standup(
        [t.task_data for t in sprint.tasks],
        sprint.config_snapshot,
        sprint_start, standup_date, hours_per_day, role_filter,
    )


@router.get("/{sprint_id}/gantt", response_model=list[GanttItem])
def get_gantt(
    sprint_id: int,
    start_date: date = Query(..., description="Дата начала спринта, напр. 2025-01-20"),
    hours_per_day: float = Query(8.0, ge=1, le=24),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id)
    vac_dicts = repository.vacations_to_dicts(repository.list_vacations(db, config.id))
    return compute_gantt_schedule(
        [t.task_data for t in sprint.tasks],
        sprint.config_snapshot, start_date, hours_per_day,
        dependencies=sprint.task_dependencies or [],
        vacations=vac_dicts,
    )


# -------------------- Dependencies CRUD --------------------

@router.get("/{sprint_id}/dependencies", response_model=list[TaskDependency])
def get_dependencies(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id)
    return [TaskDependency(**d) for d in (sprint.task_dependencies or [])]


@router.post("/{sprint_id}/dependencies", response_model=list[TaskDependency], status_code=201)
def add_dependency(
    sprint_id: int,
    body: TaskDependency,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id)
    deps = list(sprint.task_dependencies or [])
    new_dep = body.model_dump()
    if new_dep not in deps:
        deps.append(new_dep)
        sprint.task_dependencies = deps
        db.commit()
    return [TaskDependency(**d) for d in sprint.task_dependencies]


@router.delete("/{sprint_id}/dependencies", status_code=204)
def remove_dependency(
    sprint_id: int,
    body: TaskDependency,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id)
    deps = list(sprint.task_dependencies or [])
    rm = body.model_dump()
    sprint.task_dependencies = [d for d in deps if d != rm]
    db.commit()


@router.delete("/{sprint_id}", status_code=204)
def delete_one(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    try:
        sprints_service.delete_draft(db, sprint_id, config.id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    except SprintNotADraftError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{sprint_id}/tasks", response_model=SprintOut)
def set_tasks(
    sprint_id: int,
    body: SetTasksRequest,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    try:
        sprint = sprints_service.set_sprint_tasks(
            db, sprint_id, config.id,
            [t.model_dump() for t in body.tasks],
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    except SprintNotADraftError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_out(sprint)
