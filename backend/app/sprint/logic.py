"""Бизнес-логика формирования спринта.

Чистые функции: принимают конфиг и Jira-клиент, возвращают данные.
Никакого print/sys.exit/глобального состояния.
"""

import re
from typing import Any

from app.jira.client import JiraClient
from app.sprint.config import SprintConfig


# -------------------- Извлечение данных --------------------

def _build_fields_param(cfg: SprintConfig, sp_field: str | None) -> str:
    fields = ["summary", "status", "assignee", "reporter",
              "timeoriginalestimate", "issuetype"]
    if sp_field:
        fields.append(sp_field)
    fields.extend(cfg.role_hours_fields.values())
    fields.append(cfg.sprint_field)
    fields.append(cfg.responsible_field)
    return ",".join(fields)


def find_story_points_field(client: JiraClient) -> str | None:
    fields = client.get("/rest/api/3/field")
    for f in fields:
        name = (f.get("name") or "").lower()
        if name in ("story points", "story point estimate"):
            return f["id"]
    return None


def fetch_board_issues(client: JiraClient, board_id: int, fields_param: str) -> list[dict]:
    issues = []
    start = 0
    while True:
        data = client.get(
            f"/rest/agile/1.0/board/{board_id}/issue",
            params={"startAt": start, "maxResults": 100, "fields": fields_param},
        )
        batch = data.get("issues", [])
        issues.extend(batch)
        total = data.get("total", 0)
        if start + len(batch) >= total or not batch:
            break
        start += len(batch)
    return issues


def fetch_component_issues(client: JiraClient, project_key: str,
                            component_name: str, fields_param: str) -> list[dict]:
    """Через JQL — постранично с использованием nextPageToken."""
    issues = []
    next_token = None
    jql = f'project = {project_key} AND component = "{component_name}"'
    while True:
        params = {"jql": jql, "fields": fields_param, "maxResults": 100}
        if next_token:
            params["nextPageToken"] = next_token
        data = client.get("/rest/api/3/search/jql", params=params)
        batch = data.get("issues", [])
        issues.extend(batch)
        next_token = data.get("nextPageToken")
        if data.get("isLast", True) or not next_token:
            break
    return issues


# -------------------- Парсинг полей --------------------

def extract_max_sprint_number(sprints_value: list | None) -> tuple[int | None, str | None]:
    if not sprints_value:
        return None, None
    best_num = None
    best_name = None
    for s in sprints_value:
        name = s.get("name") if isinstance(s, dict) else str(s)
        m = re.search(r"(\d+)", name or "")
        if not m:
            continue
        num = int(m.group(1))
        if best_num is None or num > best_num:
            best_num = num
            best_name = name
    return best_num, best_name


def estimate_hours(fields: dict, bucket: str, cfg: SprintConfig,
                    sp_field: str | None) -> float:
    """Приоритет: поле часов по бакету → timeoriginalestimate → SP*4 → дефолт."""
    role_field = cfg.bucket_hours_field.get(bucket)
    if role_field:
        v = fields.get(role_field)
        if v not in (None, "", 0):
            try:
                fv = float(v)
                if fv > 0:
                    return fv
            except (TypeError, ValueError):
                pass

    sec = fields.get("timeoriginalestimate")
    if sec:
        return round(sec / 3600, 1)
    if sp_field:
        sp = fields.get(sp_field)
        if sp:
            return float(sp) * 4
    return cfg.default_task_hours


# -------------------- Сборка кандидатов --------------------

def _process_issue(issue: dict, source_label: str, by_key: dict,
                   counters: dict, cfg: SprintConfig, base_url: str,
                   sp_field: str | None) -> None:
    f = issue["fields"]

    issuetype = (f.get("issuetype") or {}).get("name", "")
    if issuetype.lower() in ("эпик", "epic"):
        counters["skipped_epic"] += 1
        return

    status_name = f["status"]["name"]
    bucket = cfg.status_bucket.get(status_name)
    if not bucket:
        return

    assignee = f.get("assignee") or {}
    reporter = f.get("reporter") or {}
    responsible = f.get(cfg.responsible_field) or {}
    assignee_id = assignee.get("accountId")
    reporter_id = reporter.get("accountId")
    responsible_id = responsible.get("accountId") if isinstance(responsible, dict) else None

    if bucket in cfg.strict_assignee_buckets:
        if assignee_id not in cfg.team:
            counters["skipped_strict"] += 1
            return
        owner_id = assignee_id
    else:
        if assignee_id in cfg.team:
            owner_id = assignee_id
        elif responsible_id in cfg.team:
            owner_id = responsible_id
        elif reporter_id in cfg.team:
            owner_id = reporter_id
        else:
            return

    key = issue["key"]
    if key in by_key:
        return

    sprint_num, sprint_name = extract_max_sprint_number(f.get(cfg.sprint_field))

    orig_sec = f.get("timeoriginalestimate")
    orig_hours = round(orig_sec / 3600, 1) if orig_sec else None

    h_analyst = f.get(cfg.role_hours_fields["analyst"])
    h_tester = f.get(cfg.role_hours_fields["tester"])
    h_developer = f.get(cfg.role_hours_fields["developer"])

    formal_only = (
        assignee_id not in cfg.team
        and not h_analyst
        and not h_tester
    )

    by_key[key] = {
        "key": key,
        "url": f"{base_url}/browse/{key}",
        "summary": f.get("summary") or "",
        "status_name": status_name,
        "bucket": bucket,
        "owner_id": owner_id,
        "owner_file_name": cfg.team[owner_id]["file_name"],
        "hours": estimate_hours(f, bucket, cfg, sp_field),
        "board": source_label,
        "sprint_num": sprint_num,
        "sprint_name": sprint_name,
        "formal_only": formal_only,
        "hours_analyst": h_analyst,
        "hours_tester": h_tester,
        "hours_developer": h_developer,
        "hours_original": orig_hours,
    }
    counters["matched"] += 1


def collect_candidates(client: JiraClient, cfg: SprintConfig) -> tuple[list[dict], dict]:
    """Возвращает (список_кандидатов, диагностика)."""
    sp_field = find_story_points_field(client)
    fields_param = _build_fields_param(cfg, sp_field)
    base_url = client.base_url

    by_key: dict = {}
    diagnostics: dict[str, Any] = {
        "sp_field": sp_field,
        "by_source": [],
    }

    for board_name, board_id in cfg.boards.items():
        counters = {"matched": 0, "skipped_strict": 0, "skipped_epic": 0}
        try:
            issues = fetch_board_issues(client, board_id, fields_param)
        except Exception as e:
            diagnostics["by_source"].append({
                "source": board_name, "kind": "board", "error": str(e),
            })
            continue
        for it in issues:
            _process_issue(it, board_name, by_key, counters, cfg, base_url, sp_field)
        diagnostics["by_source"].append({
            "source": board_name, "kind": "board",
            "fetched": len(issues), **counters,
        })

    for component_name in cfg.extra_components:
        counters = {"matched": 0, "skipped_strict": 0, "skipped_epic": 0}
        try:
            issues = fetch_component_issues(client, cfg.project_key, component_name, fields_param)
        except Exception as e:
            diagnostics["by_source"].append({
                "source": component_name, "kind": "component", "error": str(e),
            })
            continue
        for it in issues:
            _process_issue(it, f"component:{component_name}", by_key, counters,
                           cfg, base_url, sp_field)
        diagnostics["by_source"].append({
            "source": component_name, "kind": "component",
            "fetched": len(issues), **counters,
        })

    return list(by_key.values()), diagnostics


# -------------------- Распределение по людям --------------------

def _is_estimated(task: dict) -> bool:
    if task["bucket"] == "Анализ":
        return bool(task.get("hours_analyst"))
    if task["bucket"] == "Тестирование":
        return bool(task.get("hours_tester"))
    return False


def _sort_key(task: dict, status_priority: dict[str, int]):
    return (
        0 if task.get("sprint_num") is not None else 1,
        -(task.get("sprint_num") or 0),
        0 if _is_estimated(task) else 1,
        status_priority.get(task["status_name"], 99),
        -task["hours"],
    )


def compute_priorities(candidates: list[dict], cfg: SprintConfig) -> None:
    """Проставить task['priority'] = 1..N в разрезе каждого аналитика.
    formal_only получают priority=None.
    """
    by_owner: dict[str, list[dict]] = {}
    for t in candidates:
        by_owner.setdefault(t["owner_file_name"], []).append(t)

    for tasks in by_owner.values():
        non_formal = [t for t in tasks if not t.get("formal_only")]
        non_formal.sort(key=lambda x: _sort_key(x, cfg.status_priority))
        for i, t in enumerate(non_formal, start=1):
            t["priority"] = i
        for t in tasks:
            if t.get("formal_only"):
                t["priority"] = None


def allocate(candidates: list[dict], cfg: SprintConfig) -> tuple[list[dict], list[dict], dict]:
    """Распределение задач до точного бюджета на каждого аналитика.

    Возвращает (allocated, overflow, used_hours_by_owner_id).
    """
    candidates = [c for c in candidates if not c.get("formal_only")]
    candidates.sort(key=lambda x: _sort_key(x, cfg.status_priority))

    allocated: list[dict] = []
    used: dict[str, float] = {acc_id: 0.0 for acc_id in cfg.team}
    remaining = list(candidates)

    # Проход 1: целые задачи, крупные сначала (текущий порядок сортировки)
    rest = []
    for task in remaining:
        owner = task["owner_id"]
        if used[owner] + task["hours"] <= cfg.hours_per_person:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            rest.append(task)

    # Проход 2: добор маленькими целиком
    rest.sort(key=lambda t: t["hours"])
    rest2 = []
    for task in rest:
        owner = task["owner_id"]
        if used[owner] + task["hours"] <= cfg.hours_per_person:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            rest2.append(task)

    # Проход 3: режем последнюю задачу до точного остатка
    overflow = []
    sliced_owners: set[str] = set()
    for task in rest2:
        owner = task["owner_id"]
        gap = cfg.hours_per_person - used[owner]
        if gap > 0 and owner not in sliced_owners:
            partial = task.copy()
            partial["hours"] = round(gap, 1)
            partial["partial_from"] = task["hours"]
            used[owner] = cfg.hours_per_person
            sliced_owners.add(owner)
            allocated.append(partial)
        else:
            overflow.append(task)

    return allocated, overflow, used
