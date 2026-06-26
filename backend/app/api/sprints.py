"""Эндпоинты истории спринтов (lead-only)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import current_config, get_jira_client
from app.core.i18n import get_lang, make_translator
from app.db import models, repository, sprints_repository
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.gantt import (
    GanttItem, GanttSnapshotCreate, GanttSnapshotDetail, GanttSnapshotSummary,
    StandupExecutor, TaskDependency,
)
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

_MSG: dict[str, dict[str, str]] = {
    "sprint_not_found": {"ru": "Sprint {sprint_id} не найден", "en": "Sprint {sprint_id} not found"},
    "snapshot_not_found": {"ru": "Снимок {snapshot_id} не найден", "en": "Snapshot {snapshot_id} not found"},
}
_t = make_translator(_MSG)


def _get_sprint_or_404(db: Session, sprint_id: int, config_id: int, lang: str = "ru") -> models.Sprint:
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint or sprint.config_id != config_id:
        raise HTTPException(status_code=404, detail=_t("sprint_not_found", lang, sprint_id=sprint_id))
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
    lang: str = Depends(get_lang),
):
    return _to_out(_get_sprint_or_404(db, sprint_id, config.id, lang))


@router.post("/draft", response_model=SprintOut)
def save_draft(
    body: SaveDraftRequest,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        sprint_num = sprints_service.compute_next_sprint_num(
            db, config.id, body.max_sprint_in_jira, lang=lang,
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
            lang=lang,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return _to_out(sprint)


@router.post(
    "/{sprint_id}/approve", response_model=SprintOut,
    dependencies=[Depends(get_jira_client)],
)
def approve(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        sprint = sprints_service.approve_sprint(db, client, sprint_id, config.id, lang=lang)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=_t("sprint_not_found", lang, sprint_id=sprint_id))
    except SprintNotADraftError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except JiraSprintNotFoundError as e:
        raise HTTPException(status_code=412, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))
    return _to_out(sprint)


@router.post("/{sprint_id}/reopen", response_model=SprintOut)
def reopen(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        sprint = sprints_service.reopen_sprint(db, sprint_id, config.id, lang=lang)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=_t("sprint_not_found", lang, sprint_id=sprint_id))
    except SprintNotApprovedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_out(sprint)


@router.post(
    "/{sprint_id}/close", response_model=SprintOut,
    dependencies=[Depends(get_jira_client)],
)
def close(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        sprint = sprints_service.close_sprint(db, client, sprint_id, config.id, lang=lang)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=_t("sprint_not_found", lang, sprint_id=sprint_id))
    except SprintNotApprovedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except JiraSprintNotClosedError as e:
        raise HTTPException(status_code=412, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))
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
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)

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
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    vac_dicts = repository.vacations_to_dicts(repository.list_vacations(db, config.id))
    root_tasks = {
        r.owner_id: r.task_key
        for r in repository.list_root_tasks(db, config.id, f"sprint-{sprint.sprint_num}")
    }
    return compute_gantt_schedule(
        [t.task_data for t in sprint.tasks],
        sprint.config_snapshot, start_date, hours_per_day,
        dependencies=sprint.task_dependencies or [],
        vacations=vac_dicts,
        root_tasks=root_tasks,
    )


# -------------------- Снимки Ганта --------------------

@router.post("/{sprint_id}/gantt/snapshots", response_model=GanttSnapshotSummary, status_code=201)
def create_gantt_snapshot(
    sprint_id: int,
    body: GanttSnapshotCreate,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    snap = sprints_repository.create_gantt_snapshot(
        db, sprint.id, body.gantt_start, body.hours_per_day,
        [item.model_dump() for item in body.gantt_items], body.label,
    )
    return GanttSnapshotSummary(
        id=snap.id, captured_at=snap.captured_at.isoformat(),
        label=snap.label, gantt_start=snap.gantt_start, hours_per_day=snap.hours_per_day,
    )


@router.get("/{sprint_id}/gantt/snapshots", response_model=list[GanttSnapshotSummary])
def list_gantt_snapshots(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    return [
        GanttSnapshotSummary(
            id=s.id, captured_at=s.captured_at.isoformat(),
            label=s.label, gantt_start=s.gantt_start, hours_per_day=s.hours_per_day,
        )
        for s in sprints_repository.list_gantt_snapshots(db, sprint.id)
    ]


@router.get("/{sprint_id}/gantt/snapshots/{snapshot_id}", response_model=GanttSnapshotDetail)
def get_gantt_snapshot(
    sprint_id: int,
    snapshot_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    snap = sprints_repository.get_gantt_snapshot(db, sprint.id, snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=_t("snapshot_not_found", lang, snapshot_id=snapshot_id))
    return GanttSnapshotDetail(
        id=snap.id, captured_at=snap.captured_at.isoformat(),
        label=snap.label, gantt_start=snap.gantt_start, hours_per_day=snap.hours_per_day,
        gantt_items=snap.gantt_items,
    )


@router.delete("/{sprint_id}/gantt/snapshots/{snapshot_id}", status_code=204)
def delete_gantt_snapshot(
    sprint_id: int,
    snapshot_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    if not sprints_repository.delete_gantt_snapshot(db, sprint.id, snapshot_id):
        raise HTTPException(status_code=404, detail=_t("snapshot_not_found", lang, snapshot_id=snapshot_id))


# -------------------- Dependencies CRUD --------------------

def _dep_identity(d: dict) -> tuple:
    """Канонический идентификатор зависимости — старые записи без from_bucket/
    to_bucket (до фазовых зависимостей) считаются эквивалентными пустым строкам."""
    return (d.get("from_key"), d.get("to_key"), d.get("from_bucket") or "", d.get("to_bucket") or "")


@router.get("/{sprint_id}/dependencies", response_model=list[TaskDependency])
def get_dependencies(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    return [TaskDependency(**d) for d in (sprint.task_dependencies or [])]


@router.post("/{sprint_id}/dependencies", response_model=list[TaskDependency], status_code=201)
def add_dependency(
    sprint_id: int,
    body: TaskDependency,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    deps = list(sprint.task_dependencies or [])
    new_dep = body.model_dump()
    if _dep_identity(new_dep) not in {_dep_identity(d) for d in deps}:
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
    lang: str = Depends(get_lang),
):
    sprint = _get_sprint_or_404(db, sprint_id, config.id, lang)
    deps = list(sprint.task_dependencies or [])
    rm = _dep_identity(body.model_dump())
    sprint.task_dependencies = [d for d in deps if _dep_identity(d) != rm]
    db.commit()


@router.delete("/{sprint_id}", status_code=204)
def delete_one(
    sprint_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        sprints_service.delete_draft(db, sprint_id, config.id, lang=lang)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=_t("sprint_not_found", lang, sprint_id=sprint_id))
    except SprintNotADraftError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{sprint_id}/tasks", response_model=SprintOut)
def set_tasks(
    sprint_id: int,
    body: SetTasksRequest,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        sprint = sprints_service.set_sprint_tasks(
            db, sprint_id, config.id,
            [t.model_dump() for t in body.tasks],
            lang=lang,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SprintAccessDeniedError:
        raise HTTPException(status_code=404, detail=_t("sprint_not_found", lang, sprint_id=sprint_id))
    except SprintNotADraftError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_out(sprint)
