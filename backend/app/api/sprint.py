"""Эндпоинты формирования спринта (lead-only)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_config, get_jira_client, require_lead
from app.api.sprints import _to_out as sprint_to_out
from app.core.i18n import get_lang
from app.db import models
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.sprint import (
    CandidatesResponse, SprintBuildRequest, SprintBuildResponse,
)
from app.schemas.sprints import SprintOut
from app.services import sprints_service
from app.services.sprint_service import (
    ConfigNotFoundError, build_sprint, collect_sprint_candidates,
)

router = APIRouter(prefix="/sprint", tags=["sprint"])


class BuildAndSaveResponse(SprintBuildResponse):
    sprint: SprintOut


def _parse_candidates_in(body: SprintBuildRequest | None) -> list[dict] | None:
    if body and body.candidates:
        return [c.model_dump() for c in body.candidates]
    return None


@router.post(
    "/candidates", response_model=CandidatesResponse,
    dependencies=[Depends(get_jira_client)],
)
def candidates(
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        result = collect_sprint_candidates(db, client, user.id, lang=lang)
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))
    return result


@router.post(
    "/build", response_model=SprintBuildResponse,
    dependencies=[Depends(get_jira_client)],
)
def build(
    body: SprintBuildRequest | None = None,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        result = build_sprint(
            db, client, user.id, candidates_in=_parse_candidates_in(body), lang=lang,
        )
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))
    return result


@router.post(
    "/build-and-save", response_model=BuildAndSaveResponse,
    dependencies=[Depends(get_jira_client)],
)
def build_and_save(
    body: SprintBuildRequest | None = None,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    candidates_in = _parse_candidates_in(body)

    if not candidates_in:
        try:
            collected = collect_sprint_candidates(db, client, config.owner_user_id, lang=lang)
        except ConfigNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except JiraError as e:
            raise HTTPException(status_code=502, detail=e.text(lang))
        candidates_in = collected["candidates"]
        max_sprint_num = collected["max_sprint_num"]
    else:
        max_sprint_num = max(
            (c.get("sprint_num") for c in candidates_in if c.get("sprint_num")),
            default=None,
        )

    try:
        target_sprint_num = sprints_service.compute_next_sprint_num(
            db, config.id, max_sprint_num,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = build_sprint(
            db, client, config.owner_user_id,
            candidates_in=candidates_in,
            target_sprint_num=target_sprint_num,
            lang=lang,
        )
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))

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

    return BuildAndSaveResponse(**result, sprint=sprint_to_out(sprint))
