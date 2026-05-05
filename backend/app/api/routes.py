"""HTTP-эндпоинты приложения."""

from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import repository
from app.db.session import get_db
from app.jira.client import client, JiraError
from app.sprint.config import from_dict
from app.sprint.excel import build_candidates_xlsx, build_sprint_xlsx
from app.sprint.logic import allocate, collect_candidates, compute_priorities


router = APIRouter()


# -------------------- Pydantic-схемы (что отдаём фронту) --------------------

class TaskOut(BaseModel):
    """Одна задача в ответе API."""
    key: str
    url: str
    summary: str
    status_name: str
    bucket: str
    owner_id: str
    owner_file_name: str
    hours: float
    board: str
    sprint_num: int | None
    sprint_name: str | None
    formal_only: bool
    priority: int | None = None
    partial_from: float | None = None
    hours_analyst: float | None
    hours_tester: float | None
    hours_developer: float | None
    hours_original: float | None


class OwnerStat(BaseModel):
    owner_id: str
    file_name: str
    used_hours: float
    budget: float


class SprintBuildResponse(BaseModel):
    allocated: list[TaskOut]
    overflow: list[TaskOut]
    candidates: list[TaskOut]
    owner_stats: list[OwnerStat]
    diagnostics: dict
    max_sprint_num: int | None


# -------------------- Здоровье / Jira --------------------

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/jira/check")
def jira_check():
    try:
        me = client.get("/rest/api/3/myself")
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"display_name": me.get("displayName"), "email": me.get("emailAddress")}


# -------------------- Sprint build --------------------

def _load_active_config(db: Session) -> dict:
    """Получить дефолтный конфиг из БД и сериализовать в dict для бизнес-логики."""
    cfg = repository.get_default_config(db)
    if not cfg:
        raise HTTPException(
            status_code=500,
            detail="Дефолтный конфиг не найден. Запусти seed или alembic upgrade head."
        )
    return repository.model_to_sprint_config_dict(cfg)


class CandidatesResponse(BaseModel):
    candidates: list[TaskOut]
    diagnostics: dict
    max_sprint_num: int | None


@router.post("/sprint/candidates", response_model=CandidatesResponse)
def fetch_candidates(db: Session = Depends(get_db)):
    """Собрать кандидатов из Jira с приоритизацией. Без allocate."""
    cfg = from_dict(_load_active_config(db))

    try:
        candidates, diagnostics = collect_candidates(client, cfg)
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))

    compute_priorities(candidates, cfg)

    max_n = max((c["sprint_num"] for c in candidates if c.get("sprint_num")), default=None)

    return CandidatesResponse(
        candidates=candidates,
        diagnostics=diagnostics,
        max_sprint_num=max_n,
    )


class SprintBuildRequest(BaseModel):
    """Опциональное тело: можно передать уже собранных кандидатов,
    чтобы не дёргать Jira повторно. Если пусто — собираем заново.
    """
    candidates: list[TaskOut] | None = None


@router.post("/sprint/build", response_model=SprintBuildResponse)
def build_sprint(body: SprintBuildRequest | None = None, db: Session = Depends(get_db)):
    """Allocate поверх кандидатов (своих или переданных)."""
    cfg = from_dict(_load_active_config(db))

    if body and body.candidates:
        # Используем то, что прислал фронт — без повторного похода в Jira
        candidates = [c.model_dump() for c in body.candidates]
        diagnostics = {"reused": True}
    else:
        try:
            candidates, diagnostics = collect_candidates(client, cfg)
        except JiraError as e:
            raise HTTPException(status_code=502, detail=str(e))
        compute_priorities(candidates, cfg)

    allocated, overflow, used = allocate([c for c in candidates], cfg)

    owner_stats = [
        OwnerStat(
            owner_id=acc_id,
            file_name=info["file_name"],
            used_hours=round(used[acc_id], 1),
            budget=cfg.hours_per_person,
        )
        for acc_id, info in cfg.team.items()
    ]

    max_n = max((c["sprint_num"] for c in candidates if c.get("sprint_num")), default=None)

    return SprintBuildResponse(
        allocated=allocated,
        overflow=overflow,
        candidates=candidates,
        owner_stats=owner_stats,
        diagnostics=diagnostics,
        max_sprint_num=max_n,
    )


# -------------------- Экспорт в xlsx --------------------

class SprintExportRequest(BaseModel):
    allocated: list[TaskOut]
    owner_stats: list[OwnerStat]
    max_sprint_num: int | None = None


class CandidatesExportRequest(BaseModel):
    candidates: list[TaskOut]
    max_sprint_num: int | None = None


def _xlsx_response(content: bytes, filename: str) -> StreamingResponse:
    encoded = quote(filename)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.post("/sprint/export")
def export_sprint(req: SprintExportRequest):
    content = build_sprint_xlsx(
        allocated=[t.model_dump() for t in req.allocated],
        owner_stats=[s.model_dump() for s in req.owner_stats],
        max_sprint_num=req.max_sprint_num,
    )
    suffix = f"_{req.max_sprint_num}" if req.max_sprint_num else ""
    return _xlsx_response(content, f"sprint{suffix}.xlsx")


@router.post("/candidates/export")
def export_candidates(req: CandidatesExportRequest):
    content = build_candidates_xlsx(
        candidates=[t.model_dump() for t in req.candidates],
    )
    suffix = f"_{req.max_sprint_num}" if req.max_sprint_num else ""
    return _xlsx_response(content, f"candidates{suffix}.xlsx")


# -------------------- Конфиг --------------------

class ConfigOut(BaseModel):
    """То, как конфиг отдаётся клиенту."""
    id: int
    name: str
    is_default: bool
    project_key: str
    sprint_field: str
    responsible_field: str
    hours_per_person: float
    default_task_hours: float
    team: dict[str, dict[str, str]]
    boards: dict[str, int]
    extra_components: list[str]
    status_bucket: dict[str, str]
    status_priority: dict[str, int]
    bucket_hours_field: dict[str, str]
    role_hours_fields: dict[str, str]
    strict_assignee_buckets: list[str]


def _config_to_out(cfg) -> ConfigOut:
    data = repository.model_to_sprint_config_dict(cfg)
    return ConfigOut(
        id=cfg.id,
        name=cfg.name,
        is_default=cfg.is_default,
        project_key=data["project_key"],
        sprint_field=data["sprint_field"],
        responsible_field=data["responsible_field"],
        hours_per_person=data["hours_per_person"],
        default_task_hours=data["default_task_hours"],
        team=data["team"],
        boards=data["boards"],
        extra_components=data["extra_components"],
        status_bucket=data["status_bucket"],
        status_priority=data["status_priority"],
        bucket_hours_field=data["bucket_hours_field"],
        role_hours_fields=data["role_hours_fields"],
        strict_assignee_buckets=sorted(data["strict_assignee_buckets"]),
    )


class ConfigSummary(BaseModel):
    id: int
    name: str
    is_default: bool


@router.get("/configs", response_model=list[ConfigSummary])
def list_configs(db: Session = Depends(get_db)):
    items = repository.list_configs(db)
    return [ConfigSummary(id=c.id, name=c.name, is_default=c.is_default) for c in items]


@router.get("/configs/default", response_model=ConfigOut)
def get_default_config(db: Session = Depends(get_db)):
    cfg = repository.get_default_config(db)
    if not cfg:
        raise HTTPException(status_code=404, detail="Дефолтный конфиг не найден")
    return _config_to_out(cfg)


@router.get("/configs/{config_id}", response_model=ConfigOut)
def get_config(config_id: int, db: Session = Depends(get_db)):
    cfg = repository.get_config(db, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    return _config_to_out(cfg)


class ConfigUpdate(BaseModel):
    """Тело запроса для обновления конфига. Все поля опциональны —
    обновляем только то, что прислано.
    """
    name: str | None = None
    project_key: str | None = None
    sprint_field: str | None = None
    responsible_field: str | None = None
    hours_per_person: float | None = None
    default_task_hours: float | None = None
    team: dict[str, dict[str, str]] | None = None
    boards: dict[str, int] | None = None
    extra_components: list[str] | None = None
    status_bucket: dict[str, str] | None = None
    status_priority: dict[str, int] | None = None
    bucket_hours_field: dict[str, str] | None = None
    role_hours_fields: dict[str, str] | None = None
    strict_assignee_buckets: list[str] | None = None


@router.put("/configs/{config_id}", response_model=ConfigOut)
def update_config(config_id: int, body: ConfigUpdate, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    cfg = repository.update_config(db, config_id, data)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    return _config_to_out(cfg)
