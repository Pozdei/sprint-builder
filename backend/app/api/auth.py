"""Эндпоинты аутентификации."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import models
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services.auth_service import AuthError, authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_out(u: models.User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        is_active=u.is_active,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = authenticate(db, body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return LoginResponse(access_token=token, user=_to_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return _to_user_out(user)
