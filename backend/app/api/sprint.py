"""Эндпоинты формирования спринта."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.sprint import (
    CandidatesResponse, SprintBuildRequest, SprintBuildResponse,
)
from app.schemas.sprints import SprintOut
from app.services import config_service, sprints_service
from app.services.sprint_service import (
    ConfigNotFoundError, build_sprint, collect_sprint_candidates,
)

router = APIRouter(prefix="/sprint", tags=["sprint"])


@router.post("/candidates", response_model=CandidatesResponse)
def candidates(db: Session = Depends(get_db)):
    """Собрать кандидатов из Jira (без allocate)."""
    try:
        result = collect_sprint_candidates(db, client)
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


@router.post("/build", response_model=SprintBuildResponse)
def build(body: SprintBuildRequest | None = None, db: Session = Depends(get_db)):
    """Распределить кандидатов по людям до 80ч. БЕЗ сохранения в БД.

    target_sprint_num не передаётся — псевдо-задачи попадут только recurring.
    """
    candidates_in = None
    if body and body.candidates:
        candidates_in = [c.model_dump() for c in body.candidates]
    try:
        result = build_sprint(db, client, candidates_in=candidates_in)
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


class BuildAndSaveResponse(SprintBuildResponse):
    sprint: SprintOut


@router.post("/build-and-save", response_model=BuildAndSaveResponse)
def build_and_save(body: SprintBuildRequest | None = None, db: Session = Depends(get_db)):
    """Allocate + автосохранение в БД как draft, атомарно.

    Порядок:
      1. Собрать кандидатов (или взять из тела запроса).
      2. Вычислить target_sprint_num по формуле max(max_jira, max_approved + 1).
      3. Allocate с этим номером (для фильтрации разовых псевдо-задач).
      4. Сохранить как draft.
    """
    candidates_in = None
    if body and body.candidates:
        candidates_in = [c.model_dump() for c in body.candidates]

    # 1) Если кандидаты не переданы — соберём отдельно, чтобы получить max_sprint_num
    if not candidates_in:
        try:
            collected = collect_sprint_candidates(db, client)
        except ConfigNotFoundError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except JiraError as e:
            raise HTTPException(status_code=502, detail=str(e))
        candidates_in = collected["candidates"]
        max_sprint_num = collected["max_sprint_num"]
    else:
        max_sprint_num = max(
            (c.get("sprint_num") for c in candidates_in if c.get("sprint_num")),
            default=None,
        )

    # 2) Вычисляем target_sprint_num
    try:
        target_sprint_num = sprints_service.compute_next_sprint_num(db, max_sprint_num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3) Allocate с известным номером
    try:
        result = build_sprint(
            db, client,
            candidates_in=candidates_in,
            target_sprint_num=target_sprint_num,
        )
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 4) Сохраняем
    config = config_service.get_default(db)
    if not config:
        raise HTTPException(status_code=500, detail="Дефолтный конфиг не найден")

    try:
        sprint = sprints_service.save_draft(
            db,
            sprint_num=target_sprint_num,
            config=config,
            allocated=result["allocated"],
            owner_stats=result["owner_stats"],
            max_sprint_in_jira=max_sprint_num,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    sprint_out = SprintOut(
        id=sprint.id,
        sprint_num=sprint.sprint_num,
        status=sprint.status,  # type: ignore[arg-type]
        created_at=sprint.created_at,
        approved_at=sprint.approved_at,
        max_sprint_in_jira=sprint.max_sprint_in_jira,
        config_snapshot=sprint.config_snapshot,
        owner_stats=sprint.owner_stats_snapshot,
        tasks=[t.task_data for t in sprint.tasks],
    )

    return BuildAndSaveResponse(**result, sprint=sprint_out)
