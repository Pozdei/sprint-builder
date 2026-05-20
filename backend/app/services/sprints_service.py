"""Сервис истории спринтов: формула номера, утверждение/закрытие/врывы."""

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
    pass


# -------------------- Проверка доступа --------------------

def _check_access(sprint: models.Sprint, config_id: int) -> None:
    if sprint.config_id != config_id:
        raise SprintAccessDeniedError(
            f"Sprint {sprint.id} принадлежит другому пользователю."
        )


# -------------------- Формула номера --------------------

def compute_next_sprint_num(db: Session, config_id: int, max_jira: int | None) -> int:
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


# -------------------- Ручное редактирование --------------------

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
    """Получить статус задачи и объект целевого спринта (с тем же номером)."""
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
            if int(m.group(1)) == target_sprint_num:
                target_sprint = s
                break

    return {"status_name": status_name, "target_sprint": target_sprint}


# ---------- Поиск jira_sprint_id из snapshot задач ----------

def _find_jira_sprint_id(jira: JiraClient, snapshot: dict,
                         tasks: list[models.SprintTask], target_num: int) -> int | None:
    """Найти Jira-ID спринта target_num через любую из задач снапшота."""
    sprint_field = snapshot.get("sprint_field", "")
    for st in tasks:
        td = st.task_data or {}
        if td.get("is_pseudo"):
            continue
        key = td.get("key")
        if not key:
            continue
        try:
            data = jira.get(f"/rest/api/3/issue/{key}",
                            params={"fields": sprint_field})
        except Exception:
            continue
        sprints = (data.get("fields") or {}).get(sprint_field) or []
        if not isinstance(sprints, list):
            continue
        for s in sprints:
            if not isinstance(s, dict):
                continue
            m = re.search(r"(\d+)", s.get("name") or "")
            if m and int(m.group(1)) == target_num:
                sid = s.get("id")
                if isinstance(sid, int):
                    return sid
                try:
                    return int(sid)
                except (TypeError, ValueError):
                    return None
    return None


# ---------- Логика владения и часов для врыва ----------

def _bucket_and_role_for_intrusion(
    issue: dict, snapshot: dict, role: str,
) -> str | None:
    """Если у роли есть бакет под текущий статус — вернёт имя бакета."""
    status_name = (issue.get("fields", {}).get("status") or {}).get("name", "")
    for rsb in snapshot.get("role_status_buckets", []):
        if rsb.get("role") == role and rsb.get("jira_status") == status_name:
            return rsb.get("bucket")
    return None


def _resolve_owner_in_team_snapshot(
    issue: dict, role: str, snapshot: dict,
) -> dict | None:
    """Найти владельца ТОЛЬКО в team из snapshot. Возвращает запись team или None."""
    team = snapshot.get("team", {})  # acc_id -> {jira_name, file_name, role}
    fields = issue.get("fields") or {}

    # Кандидаты в порядке приоритета:
    candidates: list[str] = []
    assignee = fields.get("assignee")
    if isinstance(assignee, dict) and assignee.get("accountId"):
        candidates.append(assignee["accountId"])

    if role == "analyst":
        resp_field = snapshot.get("responsible_field")
        if resp_field:
            resp = fields.get(resp_field)
            if isinstance(resp, dict) and resp.get("accountId"):
                candidates.append(resp["accountId"])
        reporter = fields.get("reporter")
        if isinstance(reporter, dict) and reporter.get("accountId"):
            candidates.append(reporter["accountId"])

    # Берём первого, кто (а) в team, (б) с этой ролью.
    # NB: в team могут быть несколько записей одного человека с разными ролями —
    # в нашей модели team — это dict acc_id -> single role. На сегодняшний момент
    # это ОК: если человек должен быть и аналитиком, и разрабом, он две team_member
    # записи. Но в snapshot.team (dict) останется только одна — это известная
    # ограничение модели. Пока живём с этим.
    for acc_id in candidates:
        info = team.get(acc_id)
        if info and info.get("role") == role:
            return {"account_id": acc_id, **info}
    return None


def _estimate_hours_intrusion(
    issue: dict, snapshot: dict, role: str, bucket: str,
) -> float:
    """Оценка часов врыва — упрощённая (без поля приоритетов как в основной логике).

    1. Поле часов по бакету (если есть customfield).
    2. timeoriginalestimate в секундах → часы.
    3. role_status_default_hours для (роль, статус).
    4. default_task_hours из конфига.
    """
    fields = issue.get("fields") or {}
    role_hours_fields: dict = snapshot.get("role_hours_fields") or {}
    # Поле часов привязано к роли, не к бакету. Берём напрямую.
    field_id = role_hours_fields.get(role)
    if field_id:
        val = fields.get(field_id)
        if val and float(val) > 0:
            return float(val)

    # timeoriginalestimate — секунды
    teo = fields.get("timeoriginalestimate")
    if teo:
        try:
            return round(float(teo) / 3600.0, 1)
        except (TypeError, ValueError):
            pass

    # role_status_default_hours
    status_name = (fields.get("status") or {}).get("name", "")
    for rsdh in snapshot.get("role_status_default_hours", []):
        if rsdh.get("role") == role and rsdh.get("jira_status") == status_name:
            return float(rsdh.get("hours") or 0)

    return float(snapshot.get("default_task_hours") or 12.0)


def _build_intrusion_record(
    issue: dict, snapshot: dict, terminal_set: set[str],
) -> dict | None:
    """Из jira-issue построить запись врыва. Если ни одна роль не подошла — None.

    Учитываем только реальных владельцев из team из snapshot.
    Если задача релевантна нескольким ролям — берём ПЕРВУЮ, где есть владелец.
    """
    fields = issue.get("fields") or {}
    status_name = (fields.get("status") or {}).get("name", "")

    # Перебираем включённые роли из snapshot
    roles = [r for r in snapshot.get("roles", []) if r.get("enabled")]

    for role_def in roles:
        role = role_def.get("name")
        bucket = _bucket_and_role_for_intrusion(issue, snapshot, role)
        if not bucket:
            continue
        owner = _resolve_owner_in_team_snapshot(issue, role, snapshot)
        if not owner:
            continue
        hours = _estimate_hours_intrusion(issue, snapshot, role, bucket)

        base_url = (snapshot.get("project_key") and
                     f"https://itlime.atlassian.net/browse/{issue.get('key')}") or ""

        return {
            "key": issue.get("key"),
            "summary": fields.get("summary") or "",
            "status_name": status_name,
            "is_done": status_name in terminal_set,
            "owner_id": owner["account_id"],
            "owner_file_name": owner.get("file_name") or "",
            "owner_jira_name": owner.get("jira_name") or "",
            "role": role,
            "bucket": bucket,
            "hours": hours,
            "url": base_url,
        }

    return None


# ---------- Главная функция close ----------

def close_sprint(db: Session, jira: JiraClient,
                  sprint_id: int, config_id: int) -> models.Sprint:
    """Закрыть approved-спринт.

    1. Снять снапшот статусов всех своих задач (как раньше).
    2. Найти jira_sprint_id, через JQL собрать ВСЕ задачи Jira-спринта.
    3. Diff: что есть в Jira, но нет в snapshot.tasks → врывы.
    4. Для каждого врыва найти владельца из team_snapshot — если нашёлся, добавить.
    5. Сохранить intrusions в Sprint.
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

    snapshot = sprint.config_snapshot or {}
    sprint_field = snapshot.get("sprint_field", "")
    project_key = snapshot.get("project_key", "")
    target_num = sprint.sprint_num
    terminal_set = set(snapshot.get("terminal_statuses") or [])

    # ---------- Часть 1: снапшот статусов наших задач ----------

    closed_data_by_position: dict[int, dict] = {}
    jira_complete_date: datetime | None = None
    found_closed = False
    seen_states: dict[str, int] = {}

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
                f"Возможно, все задачи переназначены."
            )
        raise JiraSprintNotClosedError(msg)

    # ---------- Часть 2: поиск врывов ----------

    intrusions: list[dict] = []
    jira_sprint_id = _find_jira_sprint_id(jira, snapshot, sprint.tasks, target_num)
    if jira_sprint_id is None:
        # Не страшно — просто не сможем посчитать врывы. Сохраним пустой список.
        print(f"[close_sprint] Не удалось определить Jira-ID спринта {target_num}, "
              f"врывы не считаем.")
    else:
        # Какие задачи мы знали при approve
        known_keys: set[str] = set()
        for st in sprint.tasks:
            td = st.task_data or {}
            if td.get("is_pseudo"):
                continue
            k = td.get("key")
            if k:
                known_keys.add(k)

        # Поля для JQL — стандартные + customfields для часов и Ответственного
        fields_list = ["summary", "status", "assignee", "reporter", "timeoriginalestimate"]
        # Добавим customfields из role_hours_fields
        for fid in (snapshot.get("role_hours_fields") or {}).values():
            if fid and fid not in fields_list:
                fields_list.append(fid)
        resp_field = snapshot.get("responsible_field")
        if resp_field and resp_field not in fields_list:
            fields_list.append(resp_field)

        jql = f'project = {project_key} AND sprint = {jira_sprint_id}'
        try:
            data = jira.get(
                "/rest/api/3/search/jql",
                params={
                    "jql": jql,
                    "fields": ",".join(fields_list),
                    "maxResults": 200,
                },
            )
            issues = data.get("issues", []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[close_sprint] Не удалось получить задачи Jira-спринта: {e}")
            issues = []

        for issue in issues:
            if not isinstance(issue, dict):
                continue
            key = issue.get("key")
            if not key or key in known_keys:
                continue
            rec = _build_intrusion_record(issue, snapshot, terminal_set)
            if rec:
                intrusions.append(rec)

    # ---------- Часть 3: сохранение ----------

    return sprints_repository.close_sprint(
        db, sprint, closed_data_by_position, jira_complete_date,
        intrusions=intrusions,
    )
