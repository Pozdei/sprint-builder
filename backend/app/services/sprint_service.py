"""Sprint service — бизнес-логика формирования спринта.

Эндпоинты вызывают только функции отсюда. Сервис не знает про HTTP,
не знает про Pydantic, работает с обычными dict'ами и Session.

Преобразование dict → Pydantic делает уровень эндпоинтов.
"""

from sqlalchemy.orm import Session

from app.db import repository
from app.jira.client import JiraClient
from app.sprint.config import from_dict
from app.sprint.logic import allocate, collect_candidates, compute_priorities


class ConfigNotFoundError(Exception):
    """Дефолтный конфиг не найден в БД (нужно запустить seed/миграции)."""


def _load_active_config(db: Session):
    """Достать дефолтный конфиг и превратить в SprintConfig."""
    cfg_model = repository.get_default_config(db)
    if not cfg_model:
        raise ConfigNotFoundError(
            "Дефолтный конфиг не найден. Выполни alembic upgrade head и перезапусти бэкенд."
        )
    return from_dict(repository.model_to_sprint_config_dict(cfg_model))


def collect_sprint_candidates(db: Session, jira: JiraClient) -> dict:
    """Собрать кандидатов из Jira с приоритизацией. Без allocate.

    Возвращает dict с ключами: candidates (list[dict]), diagnostics, max_sprint_num.
    """
    cfg = _load_active_config(db)
    candidates, diagnostics = collect_candidates(jira, cfg)
    compute_priorities(candidates, cfg)
    max_n = max((c["sprint_num"] for c in candidates if c.get("sprint_num")), default=None)
    return {
        "candidates": candidates,
        "diagnostics": diagnostics,
        "max_sprint_num": max_n,
    }


def build_sprint(
    db: Session,
    jira: JiraClient,
    candidates_in: list[dict] | None = None,
    target_sprint_num: int | None = None,
) -> dict:
    """Сформировать спринт: allocate поверх кандидатов.

    target_sprint_num — номер целевого спринта (для фильтра разовых псевдо-задач).
    Если не передан — будут использованы только recurring-задачи + автоматическое
    добавление "Руководство" для лидов.

    Если candidates_in передан — используем его (без повторного похода в Jira).
    Иначе — собираем сами.
    """
    cfg = _load_active_config(db)

    if candidates_in:
        candidates = candidates_in
        diagnostics = {"reused": True}
    else:
        candidates, diagnostics = collect_candidates(jira, cfg)
        compute_priorities(candidates, cfg)

    allocated, overflow, used = allocate([c for c in candidates], cfg, target_sprint_num)

    owner_stats = [
        {
            "owner_id": acc_id,
            "file_name": info["file_name"],
            "used_hours": round(used[acc_id], 1),
            "budget": cfg.hours_per_person,
        }
        for acc_id, info in cfg.team.items()
    ]

    max_n = max((c["sprint_num"] for c in candidates if c.get("sprint_num")), default=None)

    return {
        "allocated": allocated,
        "overflow": overflow,
        "candidates": candidates,
        "owner_stats": owner_stats,
        "diagnostics": diagnostics,
        "max_sprint_num": max_n,
    }
