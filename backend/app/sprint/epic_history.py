"""Реконструкция историчных фаз задачи по changelog Jira.

Фаза = непрерывный интервал, в течение которого задача находилась в статусе,
относящемся к некоторому bucket (Анализ / Разработка / Тестирование / …).
Владелец фазы — assignee на момент входа в неё (как в Jira: «перевели в
разработку на Самарина» → фаза разработки на Самарине).

Длительность бара берётся по фактическим датам переходов статусов, а часы для
расчёта стоимости — по плановой оценке задачи (`estimate_hours_for_role`).
"""

from datetime import date, datetime, timedelta

from app.sprint.config import SprintConfig
from app.sprint.gantt import WORK_START_HOUR, _date_to_work_hour
from app.sprint.logic import (
    _enabled_roles_by_status,
    _find_direction,
    _has_real_estimate,
    _role_allowed_buckets,
    estimate_hours_for_role,
)


def _parse_jira_dt(s: str | None) -> datetime | None:
    """'2025-01-20T14:30:00.000+0300' → naive datetime (без таймзоны)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19])
    except ValueError:
        return None


def dt_to_work_hours(
    dt: datetime, origin: date, hours_per_day: float, *, end: bool = False
) -> float:
    """Datetime → рабочие часы от origin (выходные пропускаются).

    end=False → выходной снапается вперёд (к началу след. рабочего дня);
    end=True  → назад (к концу пред. рабочего дня).
    """
    d = dt.date()
    step = timedelta(days=-1) if end else timedelta(days=1)
    guard = 0
    while d.weekday() >= 5 and guard < 7:
        d += step
        guard += 1
    base = _date_to_work_hour(d, origin, hours_per_day)
    if base is None:
        base = 0.0
    frac = (dt.hour + dt.minute / 60.0) - WORK_START_HOUR
    frac = max(0.0, min(hours_per_day, frac))
    return base + frac


def _status_transitions(issue: dict) -> tuple[str | None, list[tuple[datetime, str]]]:
    """(начальный статус, [(dt, to_status), ...] по возрастанию)."""
    histories = issue.get("changelog", {}).get("histories", [])
    raw: list[tuple[datetime | None, str | None, str | None]] = []
    for entry in histories:
        dt = _parse_jira_dt(entry.get("created"))
        for item in entry.get("items", []):
            if item.get("field") == "status":
                raw.append((dt, item.get("fromString"), item.get("toString")))
    raw.sort(key=lambda x: x[0] or datetime.min)
    initial = raw[0][1] if raw else None
    transitions = [(dt, to) for dt, _frm, to in raw if dt and to]
    return initial, transitions


def _assignee_transitions(
    issue: dict,
) -> tuple[tuple[str | None, str | None], list[tuple[datetime, str | None, str | None]]]:
    """((начальный id, начальное имя), [(dt, to_id, to_name), ...])."""
    histories = issue.get("changelog", {}).get("histories", [])
    raw: list[tuple[datetime | None, str | None, str | None, str | None, str | None]] = []
    for entry in histories:
        dt = _parse_jira_dt(entry.get("created"))
        for item in entry.get("items", []):
            if item.get("field") == "assignee":
                raw.append((dt, item.get("from"), item.get("fromString"),
                            item.get("to"), item.get("toString")))
    raw.sort(key=lambda x: x[0] or datetime.min)
    initial = (raw[0][1], raw[0][2]) if raw else (None, None)
    changes = [(dt, to_id, to_name) for dt, _fi, _fn, to_id, to_name in raw if dt]
    return initial, changes


def _assignee_at(
    dt: datetime,
    initial: tuple[str | None, str | None],
    changes: list[tuple[datetime, str | None, str | None]],
    current: tuple[str | None, str | None],
) -> tuple[str | None, str | None]:
    """(account_id, display_name) исполнителя на момент dt."""
    who_id, who_name = initial
    for cdt, to_id, to_name in changes:
        if cdt <= dt:
            who_id, who_name = to_id, to_name
        else:
            break
    if who_id is None:
        who_id, who_name = current
    return who_id, who_name


_STATUS_BUCKET_KEYWORDS: list[tuple[list[str], str, str]] = [
    # (ключевые слова в статусе, bucket, role-fallback)
    (["разраб", "код", "ревью"], "Разработка", "developer"),
    (["тест"],                   "Тестирование", "tester"),
    (["анализ", "в работе", "новый", "создан"], "Анализ", "analyst"),
]

# Когда между сменой статуса и сменой assignee прошло меньше этого порога —
# считаем их одновременными и берём assignee ПОСЛЕ смены (Jira-автоматика часто
# проставляет статус и исполнителя с разницей в несколько секунд).
_ASSIGNEE_GRACE_SECONDS = 300  # 5 минут


def _infer_bucket_from_status(status: str) -> tuple[str, str] | None:
    """Попытаться определить (bucket, role) по ключевым словам в названии статуса."""
    s = status.lower()
    for keywords, bucket, role in _STATUS_BUCKET_KEYWORDS:
        if any(kw in s for kw in keywords):
            return bucket, role
    return None


def _pick_role_bucket(
    roles: list[tuple[str, str]], assignee_id: str | None, cfg: SprintConfig,
    status_name: str = "",
) -> tuple[str, str] | None:
    """Выбрать (role, bucket) для статуса по роли assignee.

    Порядок:
    1. Точное совпадение роли исполнителя с role_status_buckets — берём напрямую.
    2. Keyword-inference по названию статуса + проверка совместимости роли:
       разработчик не может быть в Анализе, аналитик — в Разработке и т.п.
    3. Если bucket несовместим с ролью → возвращаем None (фазу пропускаем).
    """
    assignee_role = (cfg.team.get(assignee_id or "") or {}).get("role")

    # 1. Точное совпадение роли в конфиге — самый надёжный путь
    if assignee_role:
        for role, bucket in roles:
            if role == assignee_role:
                return role, bucket

    # 2. Keyword-inference по статусу
    inferred = _infer_bucket_from_status(status_name)
    if inferred:
        inferred_bucket, inferred_role = inferred

        # Проверяем, может ли роль исполнителя работать в этом bucket
        allowed = _role_allowed_buckets(assignee_role)
        if allowed is not None and inferred_bucket not in allowed:
            return None  # несовместимо — пропустить фазу

        # Подбираем уже настроенный bucket с тем же именем, если есть
        for role, bucket in roles:
            if bucket == inferred_bucket:
                return role, inferred_bucket
        return inferred_role, inferred_bucket

    return roles[0]


def build_past_phases(
    issue: dict,
    cfg: SprintConfig,
    sp_field: str | None,
    base_url: str,
    now_dt: datetime,
) -> list[dict]:
    """Список историчных фаз задачи (dict'ы с `_start_dt`/`_end_dt` + поля GanttItem).

    Каждая фаза:
      {key, url, summary, status_name, bucket, role, owner_id, owner_file_name,
       hours, hours_is_default, is_pseudo=False, is_historical=True,
       phase_status, direction, _start_dt, _end_dt, _is_current_open}

    `_is_current_open=True` — это текущий, ещё не завершённый статус задачи
    (последний сегмент, end_dt == now_dt). Часы по нему уже учтены в прогнозе
    остатка как будущая работа (см. epic_forecast._build_with_history) — вызывающая
    сторона должна занулить hours у такой фазы, иначе стоимость задвоится.
    """
    f = issue["fields"]
    key = issue["key"]
    status_to_roles = _enabled_roles_by_status(cfg)
    created_dt = _parse_jira_dt(f.get("created")) or now_dt

    initial_status, transitions = _status_transitions(issue)
    initial_assignee, assignee_changes = _assignee_transitions(issue)
    current_assignee = (
        (f.get("assignee") or {}).get("accountId"),
        (f.get("assignee") or {}).get("displayName"),
    )

    # Сегменты статусов: (status, start_dt, end_dt)
    segments: list[tuple[str, datetime, datetime]] = []
    cur_status = initial_status or (f.get("status") or {}).get("name", "")
    cur_start = created_dt
    for dt, to in transitions:
        if dt > cur_start:
            segments.append((cur_status, cur_start, dt))
        cur_status, cur_start = to, dt
    if now_dt > cur_start:
        segments.append((cur_status, cur_start, now_dt))

    labels = f.get("labels") or []
    direction = _find_direction(labels, cfg)
    direction_name = direction["name"] if direction else None

    grace = timedelta(seconds=_ASSIGNEE_GRACE_SECONDS)

    phases: list[dict] = []
    for status, start_dt, end_dt in segments:
        roles = status_to_roles.get(status, [])
        if not roles:
            # Статус не в конфиге — пробуем keyword-inference
            inferred = _infer_bucket_from_status(status)
            if not inferred:
                continue  # Open/Backlog/Done и т.п.
            inferred_bucket, inferred_role = inferred
            roles = [(inferred_role, inferred_bucket)]
        owner_id, owner_name = _assignee_at(
            start_dt + grace, initial_assignee, assignee_changes, current_assignee,
        )
        rb = _pick_role_bucket(roles, owner_id, cfg, status_name=status)
        if rb is None:
            continue  # роль исполнителя несовместима с типом работы в этом статусе
        role, bucket = rb
        member = cfg.team.get(owner_id or "") or {}
        owner_file = member.get("file_name") or owner_name or (owner_id or "—")
        hours = estimate_hours_for_role(f, role, bucket, status, cfg, sp_field)
        phases.append({
            "key": key,
            "url": f"{base_url}/browse/{key}",
            "summary": f.get("summary") or "",
            "status_name": status,
            "bucket": bucket,
            "role": role,
            "owner_id": owner_id or "",
            "owner_file_name": owner_file,
            "hours": hours,
            "hours_is_default": not _has_real_estimate(f, bucket, cfg, sp_field),
            "is_pseudo": False,
            "is_historical": True,
            "phase_status": status,
            "direction": direction_name,
            "_start_dt": start_dt,
            "_end_dt": end_dt,
            "_is_current_open": end_dt == now_dt,
        })

    return _merge_adjacent(phases)


def _merge_adjacent(phases: list[dict]) -> list[dict]:
    """Слить соседние фазы одного bucket в одну.

    У задачи не может быть двух одновременных разработчиков (или аналитиков):
    если исполнитель сменился внутри одного bucket — значит лид делегировал работу
    следующему. Берём последнего исполнителя как фактического владельца всей фазы.
    """
    if not phases:
        return phases
    phases.sort(key=lambda p: p["_start_dt"])
    merged: list[dict] = [phases[0].copy()]
    for p in phases[1:]:
        prev = merged[-1]
        if (p["bucket"] == prev["bucket"]
                and p["_start_dt"] <= prev["_end_dt"]):
            # Продлеваем фазу и обновляем исполнителя на последнего (фактического)
            prev["_end_dt"] = max(prev["_end_dt"], p["_end_dt"])
            prev["_is_current_open"] = prev["_is_current_open"] or p["_is_current_open"]
            prev["owner_id"] = p["owner_id"]
            prev["owner_file_name"] = p["owner_file_name"]
            prev["role"] = p["role"]
        else:
            merged.append(p.copy())
    return merged
