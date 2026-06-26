"""Планировщик ежедневных Telegram-дайджестов.

Раз в минуту проверяем все конфиги: у кого включён ежедневный дайджест и чьё
время `telegram_daily_time` (HH:MM) совпадает с текущей минутой — тем отправляем.
Сверка по строке HH:MM не требует пере-планирования при смене времени в UI.
Время — локальное серверного процесса.
"""

from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import repository
from app.db.session import SessionLocal
from app.services import telegram_service

_scheduler: BackgroundScheduler | None = None


def _tick() -> None:
    now_hhmm = datetime.now().strftime("%H:%M")
    db = SessionLocal()
    try:
        for config in repository.list_configs(db):
            if not getattr(config, "telegram_daily_enabled", False):
                continue
            if not config.telegram_chat_id:
                continue
            if (config.telegram_daily_time or "") != now_hhmm:
                continue
            if not telegram_service.resolve_token(config):
                continue  # ни токена конфига, ни .env — отправлять нечем
            try:
                telegram_service.build_and_send_today(db, config)
                print(f"[telegram] Дайджест отправлен: конфиг {config.id} ({config.name})")
            except Exception as e:
                print(f"[telegram] Ошибка дайджеста конфига {config.id}: {e}")
    finally:
        db.close()


def start() -> None:
    """Запустить планировщик (idempotent).

    Стартуем всегда: токен может быть задан per-конфиг, а не только в .env.
    _tick сам пропускает конфиги без эффективного токена/chat_id.
    """
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_tick, "cron", second=0, id="telegram_daily_digest")
    _scheduler.start()
    print("[telegram] Планировщик ежедневных дайджестов запущен")


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
