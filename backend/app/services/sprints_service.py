"""Сервис истории спринтов: формула номера, утверждение с проверкой Jira."""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import models, repository, sprints_repository
from app.jira.client import JiraClient


class JiraSprintNotFoundError(Exception):
    """В Jira нет спринта с таким номером — нельзя утвердить."""


class SprintNotADraftError(Exception):
    """Попытка утвердить или удалить approved-спринт."""


# -------------------- Формула номера --------------------

def compute_next_sprint_num(db: Session, max_jira: int | None) -> int:
    """Номер нового draft-спринта.

    Логика:
      new = max(max_jira, max_approved_в_бд + 1)

    Кейсы:
      max_jira=26, нет approved        → 26
      max_jira=26, approved=26          → 27 (max(26, 27) = 27)
      max_jira=27, approved=26          → 27 (max(27, 27) = 27)
      max_jira=None, approved=26        → 27 (если в Jira пусто, всё равно идём вперёд)
      max_jira=None, нет approved       → ошибка (мы не знаем с чего начать)
    """
    max_approved = sprints_repository.get_max_approved_num(db)

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
    """Сохранить allocated как draft под указанным номером.

    Если есть approved с таким номером — это ошибка (не должна возникнуть, потому
    что compute_next_sprint_num уже учёл +1). Защитимся на всякий случай.
    """
    # Проверка: нет ли approved с этим номером
    for existing in sprints_repository.list_sprints(db):
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
        sprint_num=sprint_num,
        config_snapshot=config_snapshot,
        owner_stats=owner_stats,
        tasks=allocated,
        max_sprint_in_jira=max_sprint_in_jira,
    )


# -------------------- Утверждение --------------------

def _sprint_exists_in_jira(jira: JiraClient, project_key: str,
                           sprint_field: str, sprint_num: int) -> bool:
    """Есть ли в Jira хотя бы одна задача со спринтом номер N в указанном проекте.

    Самый простой способ проверить факт существования спринта — JQL-запрос
    по полю Sprint. Если что-то нашлось — значит, спринт создан.

    Имя спринта мы извлекаем регуляркой из выборки — sprint содержит N.
    """
    # JQL по customfield — на стороне Jira подсветится по имени, но мы можем
    # просто запросить пару задач из проекта и посмотреть их sprint-поле
    # на наличие нужного номера. Это надёжнее, чем match по имени.
    #
    # На больших проектах эффективнее искать по полю Sprint через JQL.
    # Сейчас делаем максимально просто и надёжно — берём небольшую выборку
    # задач у которых поле sprint вообще заполнено.
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


def approve_sprint(db: Session, jira: JiraClient, sprint_id: int) -> models.Sprint:
    """Утвердить draft. Требует, чтобы в Jira уже существовал Sprint с таким номером."""
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
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

def delete_draft(db: Session, sprint_id: int) -> None:
    """Удалить draft. Approved/closed удалить нельзя — это требует ручного вмешательства."""
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    if sprint.status != "draft":
        raise SprintNotADraftError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"удалить можно только draft."
        )
    sprints_repository.delete_sprint(db, sprint)


# -------------------- Закрытие спринта --------------------

class SprintNotApprovedError(Exception):
    """Закрыть можно только approved-спринт."""


class JiraSprintNotClosedError(Exception):
    """Спринт в Jira ещё не закрыт (state != closed)."""


def _fetch_task_state_from_jira(
    jira: JiraClient, project_key: str, task_key: str,
    sprint_field: str,
) -> dict | None:
    """Получить актуальные данные задачи из Jira.

    Возвращает dict со статусом и состоянием спринта в Jira, или None
    если задача не найдена.
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

    # Найдём релевантный спринт по номеру в имени, чтобы получить его state и completeDate
    sprints = fields.get(sprint_field) or []
    sprint_info = None
    if sprints and isinstance(sprints, list):
        # Берём с максимальным номером (последний)
        best = None
        best_num = -1
        for s in sprints:
            if not isinstance(s, dict):
                continue
            name = s.get("name") or ""
            m = re.search(r"(\d+)", name)
            if m:
                num = int(m.group(1))
                if num > best_num:
                    best_num = num
                    best = s
        sprint_info = best

    return {
        "status_name": status_name,
        "sprint": sprint_info,  # dict with id, name, state, startDate, endDate, completeDate
    }


def close_sprint(db: Session, jira: JiraClient, sprint_id: int) -> models.Sprint:
    """Перевести approved → closed. Снять снапшот статусов задач из Jira.

    Проверяем, что хотя бы одна реальная задача спринта показывает state='closed'
    у спринта в Jira. Если нет — не даём закрыть.

    Для каждой реальной задачи (не псевдо) дёргаем Jira за актуальным статусом
    и записываем в closed_task_data.

    Псевдо-задачи не трогаем.
    """
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    if sprint.status != "approved":
        raise SprintNotApprovedError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"закрыть можно только approved."
        )

    project_key = sprint.config_snapshot.get("project_key", "")
    sprint_field = sprint.config_snapshot.get("sprint_field", "")

    # Собираем актуальные данные по всем не-псевдо задачам
    jira_state = None  # state спринта в Jira — определим по первой найденной задаче
    jira_complete_date = None
    closed_data_by_position: dict[int, dict] = {}

    for st in sprint.tasks:
        task = st.task_data or {}
        if task.get("is_pseudo"):
            continue
        key = task.get("key")
        if not key:
            continue
        fetched = _fetch_task_state_from_jira(jira, project_key, key, sprint_field)
        if fetched is None:
            closed_data_by_position[st.position] = {
                "status_name": "(не найдено)",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            continue

        # Запоминаем state спринта из Jira (если ещё не запомнили)
        s_info = fetched.get("sprint")
        if s_info and jira_state is None:
            jira_state = s_info.get("state")
            cd = s_info.get("completeDate")
            if cd:
                # Парсим Jira-формат "2026-05-12T14:30:00.000+0000"
                try:
                    jira_complete_date = datetime.fromisoformat(cd.replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    pass

        closed_data_by_position[st.position] = {
            "status_name": fetched["status_name"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # Проверка state спринта
    if jira_state != "closed":
        raise JiraSprintNotClosedError(
            f"В Jira спринт ещё не закрыт (state={jira_state!r}). "
            f"Сначала закрой Sprint {sprint.sprint_num} в Jira, потом возвращайся сюда."
        )

    return sprints_repository.close_sprint(
        db, sprint, closed_data_by_position, jira_complete_date,
    )


def set_sprint_tasks(db: Session, sprint_id: int, tasks: list[dict]) -> models.Sprint:
    """Заменить состав задач draft-спринта.

    Используется UI редактирования: пользователь стрелочками двигает задачи
    между кандидатами и спринтом.

    Пересчитываем owner_stats_snapshot из переданных задач — суммируем часы
    по owner_id. Бюджет (hours_per_person) берём из config_snapshot спринта.

    Approved редактировать нельзя.
    """
    sprint = sprints_repository.get_sprint(db, sprint_id)
    if not sprint:
        raise LookupError(f"Sprint {sprint_id} не найден")
    if sprint.status != "draft":
        raise SprintNotADraftError(
            f"Sprint {sprint.sprint_num} имеет статус {sprint.status}, "
            f"редактировать можно только draft."
        )

    # Пересчёт owner_stats
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
