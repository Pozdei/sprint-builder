"""Сервис истории спринтов: формула номера, утверждение/закрытие.

Все функции принимают user_id или config_id — изоляция между пользователями.
"""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import models, repository, sprints_repository
from app.jira.client import JiraClient


class JiraSprintNotFoundError(Exception):
    pass


class SprintNotADraftError(Exception):
    pass


class SprintNotApprovedError(Exception):
    pass


class JiraSprintNotClosedError(Exception):
    pass


class SprintAccessDeniedError(Exception):
    """Пользователь пытается работать с чужим спринтом."""


# -------------------- Проверка доступа --------------------

def _check_access(sprint: models.Sprint, config_id: int) -> None:
    if sprint.config_id != config_id:
        raise SprintAccessDeniedError(
            f"Sprint {sprint.id} принадлежит другому пользователю."
        )


# -------------------- Формула номера --------------------

def compute_next_sprint_num(db: Session, config_id: int, max_jira: int | None) -> int:
    """Формула: new = max(max_jira, max_approved_в_БД_конфига + 1)."""
    max_approved = sprints_repository.get_max_approved_num(db, config_id)
    candidate_from_approved = (max_approved + 1) if max_approved is not None else None

    candidates = [c for c in (max_jira, candidate_from_approved) if c is not None]
    if not candidates:
        raise ValueError(
            "Не могу определить номер спринта: в Jira нет ни одного спринта "
            "и в БД нет approved-спринтов."
        )
    return max(candidates)


# -------------------- Запись draft --------------------

def save_draft(
    db: Session,
    sprint_num: int,
    config: models.Config,
    allocated: list[dict],
    owner_stats: list[dict],
    max_sprint_in_jira: int | None,
) -> models.Sprint:
    for existing in sprints_repository.list_sprints_for_config(db, config.id):
        if existing.sprint_num == sprint_num and existing.status == "approved":
            raise ValueError(
                f"Sprint {sprint_num} уже утверждён — нельзя создать draft с тем же номером."
            )

    config_snapshot = {
        "id": config.id,
        "name": config.name,
        **repository.model_to_sprint_config_dict(config),
    }

    return sprints_repository.upsert_draft(
        db,
        config_id=config.id,
        sprint_num=sprint_num,
        config_snapshot=config_snapshot,
        owner_stats=owner_stats,
        tasks=allocated,
        max_sprint_in_jira=max_sprint_in_jira,
    )


# -------------------- Утверждение --------------------

def _sprint_exists_in_jira(jira: JiraClient, project_key: str,
                           sprint_field: str, sprint_num: int) -> bool:
    try:
        data = jira.get("/rest/api/3/search/jql", params={
            "jql": f'project = {project_key} AND sprint is not EMPTY',
            "fields": sprint_field,
            "maxResults": 100,
        })
    except Exception:
        return False

    issues = data.get("issues", [])
    for it in issues:
        sprints = (it.get("fields") or {}).get(sprint_field) or []
        for s in sprints:
            name = s.get("name") if isinstance(s, dict) else ""
            m = re.search(r"(\d+)", name or "")
            if m and int(m.group(1)) == sprint_num:
                return True
    return False


def approve_sprint(db: Session, jira: JiraClient,
                    sprint_id: int, config_id: int) -> models.Sprint:
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    _check_access(sprint, config_id)
    if sprint.status != "draft":
        raise SprintNotADraftError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"утвердить можно только draft."
        )

    project_key = sprint.config_snapshot.get("project_key", "")
    sprint_field = sprint.config_snapshot.get("sprint_field", "")

    if not _sprint_exists_in_jira(jira, project_key, sprint_field, sprint.sprint_num):
        raise JiraSprintNotFoundError(
            f"В Jira нет Sprint {sprint.sprint_num}. "
            f"Сначала создайте его в Jira, потом возвращайтесь сюда."
        )

    return sprints_repository.approve(db, sprint)


# -------------------- Удаление --------------------

def delete_draft(db: Session, sprint_id: int, config_id: int) -> None:
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    _check_access(sprint, config_id)
    if sprint.status != "draft":
        raise SprintNotADraftError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"удалить можно только draft."
        )
    sprints_repository.delete_sprint(db, sprint)


# -------------------- Ручное редактирование состава --------------------

def set_sprint_tasks(db: Session, sprint_id: int, config_id: int,
                      tasks: list[dict]) -> models.Sprint:
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    _check_access(sprint, config_id)
    if sprint.status != "draft":
        raise SprintNotADraftError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"редактировать можно только draft."
        )

    budget = sprint.config_snapshot.get("hours_per_person", 80.0)
    team = sprint.config_snapshot.get("team", {})

    used_by_owner: dict[str, float] = {}
    for t in tasks:
        owner = t.get("owner_id")
        if owner:
            used_by_owner[owner] = used_by_owner.get(owner, 0.0) + (t.get("hours") or 0.0)

    new_owner_stats = []
    for acc_id, info in team.items():
        new_owner_stats.append({
            "owner_id": acc_id,
            "file_name": info.get("file_name", ""),
            "used_hours": round(used_by_owner.get(acc_id, 0.0), 1),
            "budget": budget,
        })

    return sprints_repository.replace_tasks(db, sprint, tasks, new_owner_stats)


# -------------------- Закрытие --------------------

def _parse_jira_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _fetch_task_state_from_jira(
    jira: JiraClient, task_key: str, sprint_field: str, target_sprint_num: int,
) -> dict | None:
    """Получить актуальный статус задачи и инфо о КОНКРЕТНОМ спринте target_sprint_num
    из её sprint-поля. Спринты с другим номером (например, куда задачу переназначили)
    игнорируем.

    Возвращает:
      {
        "status_name": str,
        "target_sprint": dict | None   # объект спринта именно с номером target_sprint_num
      }
    или None если задача не найдена в Jira.
    """
    try:
        data = jira.get(
            f"/rest/api/3/issue/{task_key}",
            params={"fields": f"status,{sprint_field}"},
        )
    except Exception:
        return None

    fields = data.get("fields") or {}
    status_name = (fields.get("status") or {}).get("name", "")

    sprints = fields.get(sprint_field) or []
    target_sprint = None
    if isinstance(sprints, list):
        for s in sprints:
            if not isinstance(s, dict):
                continue
            name = s.get("name") or ""
            m = re.search(r"(\d+)", name)
            if not m:
                continue
            num = int(m.group(1))
            if num == target_sprint_num:
                target_sprint = s
                break

    return {"status_name": status_name, "target_sprint": target_sprint}


def close_sprint(db: Session, jira: JiraClient,
                  sprint_id: int, config_id: int) -> models.Sprint:
    """Закрыть спринт: снять снапшот статусов из Jira.

    Логика проверки state:
    1. По каждой реальной задаче запрашиваем её sprint-поле.
    2. В нём ищем объект с номером ТЕКУЩЕГО спринта (не больший!).
    3. Если хотя бы у одной задачи этот объект имеет state='closed' —
       считаем спринт в Jira закрытым.
    4. Если ни у одной — показываем то, что видели как наиболее частый state.
    """
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    _check_access(sprint, config_id)
    if sprint.status != "approved":
        raise SprintNotApprovedError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"закрыть можно только approved."
        )

    sprint_field = sprint.config_snapshot.get("sprint_field", "")
    target_num = sprint.sprint_num

    closed_data_by_position: dict[int, dict] = {}
    seen_states: dict[str, int] = {}  # state -> count, для понятного сообщения об ошибке
    jira_complete_date: datetime | None = None
    found_closed = False

    for st in sprint.tasks:
        task = st.task_data or {}
        if task.get("is_pseudo"):
            continue
        key = task.get("key")
        if not key:
            continue
        fetched = _fetch_task_state_from_jira(jira, key, sprint_field, target_num)
        if fetched is None:
            closed_data_by_position[st.position] = {
                "status_name": "(не найдено)",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            continue

        ts = fetched.get("target_sprint")
        if ts is not None:
            state = ts.get("state") or "unknown"
            seen_states[state] = seen_states.get(state, 0) + 1
            if state == "closed":
                found_closed = True
                cd = _parse_jira_date(ts.get("completeDate"))
                if cd and jira_complete_date is None:
                    jira_complete_date = cd

        closed_data_by_position[st.position] = {
            "status_name": fetched["status_name"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    if not found_closed:
        # Соберём понятное сообщение об ошибке
        if seen_states:
            states_summary = ", ".join(
                f"{state}={count}" for state, count in sorted(seen_states.items())
            )
            msg = (
                f"В Jira Sprint {target_num} ещё не закрыт. "
                f"Состояние по задачам спринта: {states_summary}. "
                f"Сначала закройте Sprint {target_num} в Jira."
            )
        else:
            msg = (
                f"В Jira не нашёл Sprint {target_num} ни у одной задачи спринта. "
                f"Возможно, все задачи переназначены в другой спринт."
            )
        raise JiraSprintNotClosedError(msg)

    return sprints_repository.close_sprint(
        db, sprint, closed_data_by_position, jira_complete_date,
    )
