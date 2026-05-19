"""Админ-эндпоинты: управление пользователями + обзор конфигов и спринтов."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db import models, sprints_repository, users_repository
from app.db.session import get_db
from app.schemas.auth import (
    ConfigTransferRequest, PasswordResetRequest, UserCreateRequest,
    UserOut, UserUpdateRequest,
)
from app.services import admin_service
from app.services.admin_service import AdminActionError

router = APIRouter(prefix="/admin", tags=["admin"])


# -------------------- DTO сводных --------------------

class AdminConfigSummary(BaseModel):
    id: int
    name: str
    owner_user_id: int | None
    owner_email: str | None
    owner_display_name: str | None
    sprints_count: int


class AdminSprintSummary(BaseModel):
    id: int
    sprint_num: int
    status: str
    config_id: int | None
    owner_email: str | None


# -------------------- Обзор --------------------

@router.get("/configs", response_model=list[AdminConfigSummary])
def list_configs(
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.db import repository
    items = repository.list_configs(db)
    result = []
    for cfg in items:
        owner_email = None
        owner_name = None
        if cfg.owner_user_id:
            u = db.get(models.User, cfg.owner_user_id)
            if u:
                owner_email = u.email
                owner_name = u.display_name
        result.append(AdminConfigSummary(
            id=cfg.id,
            name=cfg.name,
            owner_user_id=cfg.owner_user_id,
            owner_email=owner_email,
            owner_display_name=owner_name,
            sprints_count=len(
                sprints_repository.list_sprints_for_config(db, cfg.id)
            ),
        ))
    return result


@router.get("/sprints", response_model=list[AdminSprintSummary])
def list_sprints(
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = sprints_repository.list_all_sprints(db)
    user_cache: dict[int, models.User] = {}

    def get_owner_email(config_id: int | None) -> str | None:
        if not config_id:
            return None
        cfg = db.get(models.Config, config_id)
        if not cfg or not cfg.owner_user_id:
            return None
        if cfg.owner_user_id not in user_cache:
            u = db.get(models.User, cfg.owner_user_id)
            if u:
                user_cache[cfg.owner_user_id] = u
        u = user_cache.get(cfg.owner_user_id)
        return u.email if u else None

    return [
        AdminSprintSummary(
            id=s.id,
            sprint_num=s.sprint_num,
            status=s.status,
            config_id=s.config_id,
            owner_email=get_owner_email(s.config_id),
        )
        for s in items
    ]


# -------------------- Пользователи --------------------

def _to_user_out(u: models.User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, display_name=u.display_name,
        role=u.role, is_active=u.is_active,
    )


@router.get("/users", response_model=list[UserOut])
def list_users_endpoint(
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return [_to_user_out(u) for u in users_repository.list_users(db)]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user_endpoint(
    body: UserCreateRequest,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        u = admin_service.create_user(
            db, email=body.email, password=body.password,
            role=body.role, display_name=body.display_name,
        )
    except AdminActionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_user_out(u)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user_endpoint(
    user_id: int,
    body: UserUpdateRequest,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = users_repository.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Пользователь {user_id} не найден")

    try:
        u = admin_service.update_user(
            db, target=target,
            display_name=body.display_name,
            role=body.role,
            is_active=body.is_active,
        )
    except AdminActionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_user_out(u)


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password_endpoint(
    user_id: int,
    body: PasswordResetRequest,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = users_repository.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Пользователь {user_id} не найден")

    try:
        admin_service.reset_password(db, target, body.new_password)
    except AdminActionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}", status_code=204)
def delete_user_endpoint(
    user_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = users_repository.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Пользователь {user_id} не найден")

    try:
        admin_service.delete_user(db, target, current_admin_id=admin.id)
    except AdminActionError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------- Передача конфига --------------------

@router.post("/configs/{config_id}/transfer", response_model=AdminConfigSummary)
def transfer_config_endpoint(
    config_id: int,
    body: ConfigTransferRequest,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cfg = db.get(models.Config, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Конфиг {config_id} не найден")

    new_owner = users_repository.get_user_by_id(db, body.new_owner_user_id)
    if not new_owner:
        raise HTTPException(
            status_code=404,
            detail=f"Пользователь {body.new_owner_user_id} не найден",
        )

    try:
        cfg = admin_service.transfer_config(db, cfg, new_owner)
    except AdminActionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    sprints_count = len(sprints_repository.list_sprints_for_config(db, cfg.id))
    return AdminConfigSummary(
        id=cfg.id,
        name=cfg.name,
        owner_user_id=cfg.owner_user_id,
        owner_email=new_owner.email,
        owner_display_name=new_owner.display_name,
        sprints_count=sprints_count,
    )
