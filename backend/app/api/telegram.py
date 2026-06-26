"""Telegram-дайджест: ручная отправка «задачи на сегодня» по активному конфигу."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_config
from app.db import models
from app.db.session import get_db
from app.services import telegram_service
from app.telegram import client as tg
from app.telegram.client import TelegramError

router = APIRouter(prefix="/telegram", tags=["telegram"])


class SendResult(BaseModel):
    sent: bool
    count: int


@router.post("/test", response_model=SendResult)
def test_message(
    config: models.Config = Depends(current_config),
):
    """Отправить тестовое сообщение в чат конфига — проверка токена/chat_id."""
    if not config.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Не задан Telegram chat_id в конфиге")
    try:
        tg.send_message(
            config.telegram_chat_id,
            f"✅ Sprint Builder подключён к этому чату (конфиг «{config.name}»).",
            token=telegram_service.resolve_token(config),
        )
    except TelegramError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return SendResult(sent=True, count=0)


@router.post("/send-today", response_model=SendResult)
def send_today(
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    """Собрать дайджест на сегодня по последнему утверждённому спринту и отправить в чат конфига."""
    try:
        result = telegram_service.build_and_send_today(db, config)
    except telegram_service.DigestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TelegramError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return SendResult(**result)
