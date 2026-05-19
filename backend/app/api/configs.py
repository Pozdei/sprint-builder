"""Эндпоинты конфигов (lead-only).

Multi-config: lead может иметь несколько конфигов. /default возвращает активный.
Список — /api/configs. Создание/переключение/удаление — отдельные эндпоинты.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_config, require_lead
from app.db import models
from app.db.session import get_db
from app.schemas.config import ConfigOut, ConfigUpdate
from app.services import config_service
from app.services.config_service import ConfigServiceError

router = APIRouter(prefix="/configs", tags=["configs"])


# --------- Schemas ---------

class ConfigSummary(BaseModel):
    id: int
    name: str
    is_active: bool


class ConfigCreateRequest(BaseModel):
    name: str
    source_config_id: int | None = None  # если указан — копируем; иначе пустой


# --------- Список и активный ---------

@router.get("", response_model=list[ConfigSummary])
def list_my_configs(
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    items = config_service.list_user_configs(db, user.id)
    return [
        ConfigSummary(
            id=cfg.id,
            name=cfg.name,
            is_active=(user.active_config_id == cfg.id),
        )
        for cfg in items
    ]


@router.get("/default", response_model=ConfigOut)
def get_my_active_config(config: models.Config = Depends(current_config)):
    """Активный конфиг. Имя /default — историческое."""
    return config_service.to_out_dict(config)


@router.get("/{config_id}", response_model=ConfigOut)
def get_one(
    config_id: int,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    from app.db import repository
    cfg = repository.get_config(db, config_id)
    if not cfg or cfg.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    return config_service.to_out_dict(cfg)


@router.put("/{config_id}", response_model=ConfigOut)
def update_one(
    config_id: int,
    body: ConfigUpdate,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    from app.db import repository
    cfg = repository.get_config(db, config_id)
    if not cfg or cfg.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    data = body.model_dump(exclude_unset=True)
    updated = config_service.update(db, config_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    return config_service.to_out_dict(updated)


# --------- Создание ---------

@router.post("", response_model=ConfigOut, status_code=201)
def create_config(
    body: ConfigCreateRequest,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    try:
        if body.source_config_id is not None:
            cfg = config_service.create_config_from(
                db, user, source_config_id=body.source_config_id, name=body.name,
            )
        else:
            cfg = config_service.create_empty_config(db, user, name=body.name)
    except ConfigServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return config_service.to_out_dict(cfg)


# --------- Переключение активного ---------

@router.post("/{config_id}/activate", response_model=ConfigOut)
def activate(
    config_id: int,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    try:
        cfg = config_service.set_active_config(db, user, config_id)
    except ConfigServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return config_service.to_out_dict(cfg)


# --------- Удаление ---------

@router.delete("/{config_id}", status_code=204)
def delete_one(
    config_id: int,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    try:
        config_service.delete_config(db, user, config_id)
    except ConfigServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
