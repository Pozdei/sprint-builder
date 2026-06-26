"""Эндпоинты аутентификации."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.i18n import get_lang
from app.db import models
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services.auth_service import AuthError, authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db), lang: str = Depends(get_lang)):
    try:
        user, token = authenticate(db, body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=e.text(lang))
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return UserOut.model_validate(user)
