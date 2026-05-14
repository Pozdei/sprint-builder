"""Эндпоинты конфига."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.config import ConfigOut, ConfigSummary, ConfigUpdate
from app.services import config_service

router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("", response_model=list[ConfigSummary])
def list_all(db: Session = Depends(get_db)):
    items = config_service.list_configs(db)
    return [ConfigSummary(id=c.id, name=c.name, is_default=c.is_default) for c in items]


@router.get("/default", response_model=ConfigOut)
def get_default(db: Session = Depends(get_db)):
    cfg = config_service.get_default(db)
    if not cfg:
        raise HTTPException(status_code=404, detail="Дефолтный конфиг не найден")
    return config_service.to_out_dict(cfg)


@router.get("/{config_id}", response_model=ConfigOut)
def get_one(config_id: int, db: Session = Depends(get_db)):
    cfg = config_service.get_by_id(db, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    return config_service.to_out_dict(cfg)


@router.put("/{config_id}", response_model=ConfigOut)
def update_one(config_id: int, body: ConfigUpdate, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    cfg = config_service.update(db, config_id, data)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")
    return config_service.to_out_dict(cfg)
