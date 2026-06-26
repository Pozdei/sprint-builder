"""Telegram-дайджест «задачи на сегодня».

По последнему утверждённому спринту конфига строим Гант (Jira-free,
тем же алгоритмом, что и раздел «История»), отбираем активные сегодня бары
и отправляем сгруппированный по направлениям список в Telegram-чат конфига.
Старт Ганта — дата утверждения спринта (approved_at).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_secret
from app.db import models, repository, sprints_repository
from app.sprint import today_export
from app.sprint.gantt import compute_gantt_schedule
from app.telegram import client as tg

HOURS_PER_DAY = 8.0


class DigestError(Exception):
    """Дайджест не может быть отправлен (нет спринта, нет chat_id и т.п.)."""


def resolve_token(config: models.Config) -> str:
    """Эффективный токен бота: токен конфига (расшифрованный) → глобальный .env."""
    if config.telegram_bot_token_enc:
        return decrypt_secret(config.telegram_bot_token_enc)
    return settings.telegram_bot_token


def _gantt_for_latest_approved(db: Session, config: models.Config) -> tuple[list[dict], date]:
    """Расписание Ганта последнего утверждённого спринта + дата старта."""
    sprint = sprints_repository.get_latest_approved(db, config.id)
    if sprint is None:
        raise DigestError("Нет утверждённого спринта — нечего отправлять")

    approved = sprint.approved_at or datetime.now(timezone.utc)
    start_date = approved.date()

    vac_dicts = repository.vacations_to_dicts(repository.list_vacations(db, config.id))
    root_tasks = {
        r.owner_id: r.task_key
        for r in repository.list_root_tasks(db, config.id, f"sprint-{sprint.sprint_num}")
    }
    items = compute_gantt_schedule(
        [t.task_data for t in sprint.tasks],
        sprint.config_snapshot, start_date, HOURS_PER_DAY,
        dependencies=sprint.task_dependencies or [],
        vacations=vac_dicts,
        root_tasks=root_tasks,
    )
    return items, start_date


def build_and_send_today(db: Session, config: models.Config, today: date | None = None) -> dict:
    """Собрать дайджест на сегодня и отправить. Возвращает {sent, count}.

    Бросает DigestError, если отправлять некуда/нечего из-за конфигурации;
    tg.TelegramError — при сетевой/API-ошибке отправки.
    """
    if not config.telegram_chat_id:
        raise DigestError("Не задан Telegram chat_id в конфиге")

    today = today or datetime.now(timezone.utc).date()
    items, _ = _gantt_for_latest_approved(db, config)
    active = today_export.filter_today(items, today)

    if not active:
        text = f"{today_export._date_label(today)}\n\nНа сегодня задач нет."
    else:
        text = today_export.build_html(active, today)

    tg.send_message(config.telegram_chat_id, text, token=resolve_token(config))
    return {"sent": True, "count": len(active)}
