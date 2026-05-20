"""Sprint service — фаза 2.8: работа с активным конфигом lead-пользователя.

Все функции принимают user_id и читают его АКТИВНЫЙ конфиг через config_service.
"""

from sqlalchemy.orm import Session

from app.db import users_repository
from app.jira.client import JiraClient
from app.services import config_service
from app.sprint.config import from_dict
from app.sprint.logic import (
    allocate, collect_candidates, compute_priorities,
    compute_sprint_expected_results, derive_pipeline_tasks,
)


class ConfigNotFoundError(Exception):
    """У пользователя нет конфига (даже после ensure)."""


def _load_user_config(db: Session, user_id: int):
    """Грузим активный конфиг пользователя; если нет — ensure создаст пустой."""
    user = users_repository.get_user_by_id(db, user_id)
    if not user:
        raise ConfigNotFoundError(f"Пользователь {user_id} не найден")

    cfg_model = config_service.ensure_active_config(db, user)
    if not cfg_model:
        raise ConfigNotFoundError(
            "У вас нет активного конфига. Создайте его в шапке через 'Конфиг'."
        )
    from app.db import repository
    return from_dict(repository.model_to_sprint_config_dict(cfg_model))


def collect_sprint_candidates(db: Session, jira: JiraClient, user_id: int) -> dict:
    cfg = _load_user_config(db, user_id)
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
    user_id: int,
    candidates_in: list[dict] | None = None,
    target_sprint_num: int | None = None,
) -> dict:
    cfg = _load_user_config(db, user_id)

    if candidates_in:
        candidates = candidates_in
        diagnostics = {"reused": True}
    else:
        candidates, diagnostics = collect_candidates(jira, cfg)
        compute_priorities(candidates, cfg)

    allocated, overflow, used = allocate([c for c in candidates], cfg, target_sprint_num)

    # Породить задачи тестирования / код-ревью / дизайн-ревью из выполненных задач
    derived = derive_pipeline_tasks(allocated, cfg)
    budget = cfg.hours_per_person
    for task in derived:
        owner = task["owner_id"]
        if owner in used and used[owner] + task["hours"] <= budget:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            overflow.append(task)

    # Ожидаемый итог спринта по pipeline направлений
    expected = compute_sprint_expected_results(allocated, cfg)
    for task in allocated:
        if not task.get("is_pseudo"):
            task["sprint_expected_result"] = expected.get(task["key"])

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
