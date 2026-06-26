"""Эндпоинты конфигов (lead-only).

Multi-config: lead может иметь несколько конфигов. /default возвращает активный.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_config, require_lead
from app.core.i18n import get_lang, make_translator
from app.db import models, repository
from app.db.session import get_db
from app.schemas.config import ConfigCreateRequest, ConfigOut, ConfigSummary, ConfigTemplate, ConfigUpdate
from app.schemas.gantt import EmployeeVacationIn, EmployeeVacationOut
from app.services import config_service
from app.services.config_service import ConfigServiceError

router = APIRouter(prefix="/configs", tags=["configs"])

_MSG: dict[str, dict[str, str]] = {
    "config_not_found": {"ru": "Конфиг {id} не найден", "en": "Config {id} not found"},
    "vacation_end_before_start": {
        "ru": "Дата окончания не может быть раньше даты начала",
        "en": "End date cannot be earlier than start date",
    },
    "vacation_not_found": {"ru": "Отпуск {id} не найден", "en": "Vacation {id} not found"},
}
_t = make_translator(_MSG)


def _get_owned_config(db: Session, config_id: int, user_id: int, lang: str = "ru") -> models.Config:
    cfg = repository.get_config(db, config_id)
    if not cfg or cfg.owner_user_id != user_id:
        raise HTTPException(status_code=404, detail=_t("config_not_found", lang, id=config_id))
    return cfg


def _vacation_to_out(v: models.EmployeeVacation) -> EmployeeVacationOut:
    return EmployeeVacationOut(
        id=v.id,
        jira_account_id=v.jira_account_id,
        display_name=v.display_name,
        start_date=v.start_date,
        end_date=v.end_date,
    )


@router.get("/templates", response_model=list[ConfigTemplate])
def list_all_templates(
    _user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    """Все конфиги системы — для выбора шаблона при копировании."""
    items = repository.list_configs(db)
    return [ConfigTemplate(id=cfg.id, name=cfg.name) for cfg in items]


@router.get("", response_model=list[ConfigSummary])
def list_my_configs(
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
):
    items = config_service.list_user_configs(db, user.id)
    return [
        ConfigSummary(id=cfg.id, name=cfg.name, is_active=(user.active_config_id == cfg.id))
        for cfg in items
    ]


@router.get("/default", response_model=ConfigOut)
def get_my_active_config(config: models.Config = Depends(current_config)):
    """Активный конфиг. Имя /default — историческое."""
    return config_service.to_out_dict(config)


# -------------------- Vacations --------------------

@router.get("/vacations", response_model=list[EmployeeVacationOut])
def list_vacations(
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return [_vacation_to_out(v) for v in repository.list_vacations(db, config.id)]


@router.post("/vacations", response_model=EmployeeVacationOut, status_code=201)
def add_vacation(
    body: EmployeeVacationIn,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail=_t("vacation_end_before_start", lang))
    vac = repository.add_vacation(
        db, config.id,
        jira_account_id=body.jira_account_id,
        display_name=body.display_name,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.commit()
    return _vacation_to_out(vac)


@router.delete("/vacations/{vacation_id}", status_code=204)
def delete_vacation(
    vacation_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    ok = repository.delete_vacation(db, vacation_id, config.id)
    if not ok:
        raise HTTPException(status_code=404, detail=_t("vacation_not_found", lang, id=vacation_id))
    db.commit()


@router.get("/{config_id}", response_model=ConfigOut)
def get_one(
    config_id: int,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    cfg = _get_owned_config(db, config_id, user.id, lang)
    return config_service.to_out_dict(cfg)


@router.put("/{config_id}", response_model=ConfigOut)
def update_one(
    config_id: int,
    body: ConfigUpdate,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    _get_owned_config(db, config_id, user.id, lang)
    updated = config_service.update(db, config_id, body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail=_t("config_not_found", lang, id=config_id))
    return config_service.to_out_dict(updated)


@router.post("", response_model=ConfigOut, status_code=201)
def create_config(
    body: ConfigCreateRequest,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        if body.source_config_id is not None:
            cfg = config_service.create_config_from(
                db, user, source_config_id=body.source_config_id, name=body.name, lang=lang,
            )
        else:
            cfg = config_service.create_empty_config(db, user, name=body.name, lang=lang)
    except ConfigServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return config_service.to_out_dict(cfg)


@router.post("/{config_id}/activate", response_model=ConfigOut)
def activate(
    config_id: int,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        cfg = config_service.set_active_config(db, user, config_id, lang=lang)
    except ConfigServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return config_service.to_out_dict(cfg)


@router.delete("/{config_id}", status_code=204)
def delete_one(
    config_id: int,
    user: models.User = Depends(require_lead),
    db: Session = Depends(get_db),
    lang: str = Depends(get_lang),
):
    try:
        config_service.delete_config(db, user, config_id, lang=lang)
    except ConfigServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
