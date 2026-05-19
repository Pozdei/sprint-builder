"""Эндпоинты истории спринтов (lead-only). Фильтрация по config_id текущего пользователя."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_config
from app.db import models, sprints_repository
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.sprints import (
    ClosedTaskData, SaveDraftRequest, SetTasksRequest, SprintOut, SprintSummary,
)
from app.services import sprints_service
from app.services.sprints_service import (
    JiraSprintNotClosedError, JiraSprintNotFoundError, SprintAccessDeniedError,
    SprintNotADraftError, SprintNotApprovedError,
)

router = APIRouter(prefix="/sprints", tags=["sprints"])


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
    )


# -------------------- Просмотр --------------------

@router.get("", response_model=list[SprintSummary])
def list_all(
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    """Все спринты текущего пользователя."""
    items = sprints_repository.list_sprints_for_config(db, config.id)
    return [_to_summary(s) for s in items]


@router.get("/{sprint_id}", response_model=SprintOut)
def get_one(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    if sprint.config_id != config.id:
        raise HTTPException(status_code=404, detail=f"Sprint {sprint_id} не найден")
    return _to_out(sprint)


# -------------------- Создание draft --------------------

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


# -------------------- Утверждение --------------------

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


# -------------------- Закрытие --------------------

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


# -------------------- Удаление --------------------

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


# -------------------- Ручное редактирование --------------------

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
