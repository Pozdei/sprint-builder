"""Roadmap: сводная горизонтальная шкала по эпикам или по ручной «Детализации».

Источник задач — доски текущего конфига (как в Спринте). В Jira этих досок
нет отдельных полей "Дата старта"/"Дата окончания" — даты вычисляются из
истории смены статусов (changelog) каждой задачи:
  - старт = первый переход в статус, размеченный в role_status_buckets
    конфига (т.е. в статус, где для ЭТОГО конфига уже идёт работа);
  - окончание = последний переход в терминальный статус (cfg.terminal_statuses),
    заполняется только если задача уже начата.

Группировка (`group_by`):
  - "epic"   — по прямому родителю Jira (поле `parent`, новая иерархия задач);
  - "detail" — по ручному полю TaskDetail («задача → тема»), которое лид
    проставляет в UI страницы Roadmap. Задачи без темы в эту группировку не
    попадают — это и есть сигнал лиду доза полнить.
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.jira.client import JiraClient, current_client
from app.sprint.config import SprintConfig
from app.sprint.logic import _enabled_roles_by_status, fetch_board_issues

_FIELDS = "summary,issuetype,status,parent"
_CHANGELOG_WORKERS = 8  # серийный обход одной задачи в секунду на большом конфиге даёт минуты


def _fetch_full_changelog(client: JiraClient, key: str) -> list[dict]:
    histories: list[dict] = []
    start_at = 0
    for _ in range(50):  # предохранитель от бесконечного цикла
        data = client.get(
            f"/rest/api/3/issue/{key}/changelog",
            params={"startAt": start_at, "maxResults": 100},
        )
        values = data.get("values", [])
        histories.extend(values)
        start_at += len(values)
        if data.get("isLast", True) or not values:
            break
    return histories


def _task_dates(
    client: JiraClient, key: str, status_to_roles: dict, terminal_set: set[str],
) -> tuple[str, str]:
    """(старт, окончание) в формате YYYY-MM-DD, либо "" если не найдено."""
    start_ts, end_ts = None, None
    for h in _fetch_full_changelog(client, key):
        created = h.get("created")
        if not created:
            continue
        for item in h.get("items", []):
            if item.get("field") != "status":
                continue
            to_status = item.get("toString")
            if to_status in status_to_roles and (start_ts is None or created < start_ts):
                start_ts = created
            if to_status in terminal_set and (end_ts is None or created > end_ts):
                end_ts = created

    start = start_ts[:10] if start_ts else ""
    end = end_ts[:10] if (start and end_ts) else ""
    return start, end


def fetch_roadmap_tasks(client: JiraClient, cfg: SprintConfig) -> list[dict]:
    """Задачи со всех досок конфига + даты старта/окончания по changelog.

    Возвращает список dict: {key, summary, issuetype, boards: list[str],
    start, end, epic_key, epic_summary}.
    """
    status_to_roles = _enabled_roles_by_status(cfg)
    terminal_set = set(cfg.terminal_statuses)

    issues_by_key: dict[str, dict] = {}
    boards_by_key: dict[str, set[str]] = defaultdict(set)
    for board_name, board_id in cfg.boards.items():
        for it in fetch_board_issues(client, board_id, _FIELDS):
            issues_by_key.setdefault(it["key"], it)
            boards_by_key[it["key"]].add(board_name)

    # Сам эпик — не задача, роадмап группирует по нему, не показывает его как строку.
    task_keys = [
        key for key, issue in issues_by_key.items()
        if (issue["fields"].get("issuetype") or {}).get("name", "").lower() not in ("эпик", "epic")
    ]

    # Changelog по каждой задаче — независимые Jira-запросы, тянем пачкой воркеров,
    # иначе на конфиге с сотнями задач серийный обход занимает по несколько минут.
    real_client = current_client()
    dates_by_key: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=_CHANGELOG_WORKERS) as pool:
        futures = {
            pool.submit(_task_dates, real_client, key, status_to_roles, terminal_set): key
            for key in task_keys
        }
        for fut in as_completed(futures):
            dates_by_key[futures[fut]] = fut.result()

    rows: list[dict] = []
    for key in task_keys:
        f = issues_by_key[key]["fields"]
        parent = f.get("parent")
        epic_key = parent.get("key") if isinstance(parent, dict) else None
        epic_summary = (parent.get("fields") or {}).get("summary", "") if isinstance(parent, dict) else ""

        start, end = dates_by_key[key]

        rows.append({
            "key": key,
            "summary": f.get("summary") or "",
            "issuetype": (f.get("issuetype") or {}).get("name", ""),
            "boards": sorted(boards_by_key[key]),
            "start": start,
            "end": end,
            "epic_key": epic_key,
            "epic_summary": epic_summary,
        })
    return rows


def build_roadmap_groups(
    rows: list[dict],
    group_by: str,
    task_details: dict[str, str] | None = None,
    epic_plans: dict[str, tuple[str, str]] | None = None,
) -> list[dict]:
    """Группирует задачи по эпику (parent) или по ручной «Детализации».

    Старт группы = мин. дата старта её задач. Окончание группы = макс. дата
    окончания, но только если ВСЕ задачи группы завершены — иначе остаётся
    пустым (под ручное заполнение), группа считается "в работе".

    `epic_plans` (только для group_by="epic") — ручной план старта/окончания
    (`EpicPlan`), который лид проставляет для эпиков без реальных Jira-статусов
    (или как целевую дату поверх факта). План не переопределяет факт — оба
    значения возвращаются рядом, показываются на таймлайне одновременно.
    """
    task_details = task_details or {}
    epic_plans = epic_plans or {}
    groups: dict[str, dict] = {}

    for row in rows:
        if group_by == "epic":
            if not row["epic_key"]:
                continue
            gkey = row["epic_key"]
            glabel = f"{row['epic_key']} {row['epic_summary']}".strip()
        else:
            detail = task_details.get(row["key"], "")
            if not detail:
                continue
            gkey = detail
            glabel = detail

        g = groups.setdefault(gkey, {"key": gkey, "label": glabel, "boards": set(), "children": []})
        g["children"].append(row)
        g["boards"].update(row["boards"])

    result = []
    for g in groups.values():
        children = g["children"]
        total = len(children)
        done = sum(1 for c in children if c["end"])
        in_progress = sum(1 for c in children if c["start"] and not c["end"])
        not_started = sum(1 for c in children if not c["start"])

        starts = [c["start"] for c in children if c["start"]]
        group_start = min(starts) if starts else ""

        fully_done = total > 0 and in_progress == 0 and not_started == 0
        ends = [c["end"] for c in children if c["end"]]
        group_end = max(ends) if (fully_done and ends) else ""

        if not group_start:
            status = "not_started"
        elif group_end:
            status = "done"
        else:
            status = "in_progress"

        planned_start, planned_end = epic_plans.get(g["key"], ("", "")) if group_by == "epic" else ("", "")

        result.append({
            "key": g["key"], "label": g["label"],
            "boards": sorted(g["boards"]),
            "total": total, "done": done,
            "in_progress": in_progress, "not_started": not_started,
            "start": group_start, "end": group_end, "status": status,
            "planned_start": planned_start, "planned_end": planned_end,
        })

    # Позиция на таймлайне — по факту, а если факта ещё нет, по плану (иначе
    # ещё не начатые, но уже запланированные эпики тонут в куче "без даты").
    def sort_key(g: dict):
        pos = g["start"] or g["planned_start"]
        return (pos == "", pos, g["key"])

    result.sort(key=sort_key)
    return result
