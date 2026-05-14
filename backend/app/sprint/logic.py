"""Бизнес-логика формирования спринта — фаза 2 (мультироли).

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


# -------------------- Оценка часов --------------------

# Маппинг роли → поле часов в Jira.
# Для аналитика и тестировщика часы зависят от бакета:
#   - бакет "Анализ"        → роль "analyst"  (поле customfield_X)
#   - бакет "Тестирование"  → роль "tester"   (поле customfield_Y)
# Эта связь сейчас захардкожена. В фазе 2 явно расширяем для других ролей:
#   - бакет "Дизайн" / "Дизайн-ревью" → роль "designer"
#   - бакет "Разработка" / "Код-ревью" → роль "developer"
_BUCKET_TO_ROLE_HOURS_FIELD = {
    "Анализ":        "analyst",
    "Тестирование":  "tester",
    "Дизайн":        "designer",
    "Дизайн-ревью":  "designer",
    "Разработка":    "developer",
    "Код-ревью":     "developer",
}


def _default_hours_for(cfg: SprintConfig, role: str, status_name: str) -> float:
    """Если поля часов нет в Jira — вернуть дефолт для пары (роль, статус).

    Сначала ищем точное совпадение в role_status_default_hours.
    Если нет — общий default_task_hours.
    """
    for item in cfg.role_status_default_hours:
        if item["role"] == role and item["jira_status"] == status_name:
            return item["hours"]
    return cfg.default_task_hours


def estimate_hours_for_role(fields: dict, role: str, bucket: str,
                             status_name: str, cfg: SprintConfig,
                             sp_field: str | None) -> float:
    """Оценка часов задачи в контексте конкретной роли и бакета.

    Приоритет:
    1) Поле часов соответствующей "категории" в Jira (analyst/tester/designer/developer).
    2) timeoriginalestimate.
    3) Story Points × 4.
    4) Дефолт для пары (роль, статус) либо общий default_task_hours.
    """
    # 1) Поле часов из соответствующей роли (analyst/tester/designer/developer)
    hours_role = _BUCKET_TO_ROLE_HOURS_FIELD.get(bucket)
    if hours_role:
        field_id = cfg.role_hours_fields.get(hours_role)
        if field_id:
            v = fields.get(field_id)
            if v not in (None, "", 0):
                try:
                    fv = float(v)
                    if fv > 0:
                        return fv
                except (TypeError, ValueError):
                    pass

    # 2) Общее timeoriginalestimate
    sec = fields.get("timeoriginalestimate")
    if sec:
        return round(sec / 3600, 1)

    # 3) Story Points × 4
    if sp_field:
        sp = fields.get(sp_field)
        if sp:
            try:
                return float(sp) * 4
            except (TypeError, ValueError):
                pass

    # 4) Дефолт для пары (роль, статус) или общий
    return _default_hours_for(cfg, role, status_name)


# -------------------- Сборка кандидатов --------------------

def _team_with_role(cfg: SprintConfig, role: str) -> dict[str, dict]:
    """Отфильтровать team по конкретной роли. Возвращает {account_id: member_dict}."""
    return {
        acc_id: info
        for acc_id, info in cfg.team.items()
        if info.get("role") == role
    }


def _enabled_roles_by_status(cfg: SprintConfig) -> dict[str, list[tuple[str, str]]]:
    """Построить индекс: status -> [(role, bucket), ...] только для enabled-ролей.

    Используется в process_issue: для каждой задачи быстро находим, для каких
    ролей она актуальна.
    """
    enabled = {r["name"] for r in cfg.roles if r["enabled"]}
    index: dict[str, list[tuple[str, str]]] = {}
    for item in cfg.role_status_buckets:
        if item["role"] not in enabled:
            continue
        index.setdefault(item["jira_status"], []).append((item["role"], item["bucket"]))
    return index


def _resolve_owner(role: str, assignee_id: str | None,
                    responsible_id: str | None, reporter_id: str | None,
                    role_team: dict[str, dict]) -> str | None:
    """Вернуть accountId владельца задачи для роли — или None если задача не для нашей команды.

    - role == analyst: assignee → responsible → reporter (как раньше).
    - другие роли: только assignee.
    """
    if role == "analyst":
        if assignee_id and assignee_id in role_team:
            return assignee_id
        if responsible_id and responsible_id in role_team:
            return responsible_id
        if reporter_id and reporter_id in role_team:
            return reporter_id
        return None

    if assignee_id and assignee_id in role_team:
        return assignee_id
    return None


def _is_formal_only(role: str, assignee_id: str | None, h_analyst, h_tester) -> bool:
    """formal_only — задача без реальной работы аналитика.

    Применяется ТОЛЬКО для роли analyst: задача попала к нему через Ответственного
    или reporter, при этом в Jira не заполнены ни Время аналитика, ни Время тестировщика.
    Такие задачи остаются в кандидатах, но не идут в спринт.

    Для других ролей формальности нет — владелец только assignee, фильтр строже.
    """
    if role != "analyst":
        return False
    role_team_dummy = None  # неиспользуемо; флаг считается только когда не assignee
    if not h_analyst and not h_tester:
        # Если assignee — наш аналитик, всё ок. Если нет — formal_only.
        # Здесь мы уже знаем, что владелец нашёлся; формальность — когда assignee != наш.
        # Простое условие: нет часов аналитика/тестировщика — флаг True.
        # Но если assignee — наш аналитик, мы считаем что часы будут (просто не заполнены).
        # Поэтому проверяем именно по assignee.
        return not (assignee_id and assignee_id == _owner_was_assignee_marker(assignee_id))
    return False


def _owner_was_assignee_marker(x):
    """Заглушка: формальность считается в process_issue напрямую, без этой функции."""
    return x


def _process_issue_for_role(
    issue: dict, role: str, bucket: str, role_team: dict[str, dict],
    source_label: str, by_key_role: dict, counters: dict,
    cfg: SprintConfig, base_url: str, sp_field: str | None,
) -> None:
    """Обработать одну задачу в контексте одной роли.

    by_key_role: ключ — кортеж (jira_key, role). Так одна задача может породить
    несколько кандидатов для разных ролей, и они не пересекутся.
    """
    f = issue["fields"]

    issuetype = (f.get("issuetype") or {}).get("name", "")
    if issuetype.lower() in ("эпик", "epic"):
        counters["skipped_epic"] += 1
        return

    status_name = f["status"]["name"]

    assignee = f.get("assignee") or {}
    reporter = f.get("reporter") or {}
    responsible = f.get(cfg.responsible_field) or {}
    assignee_id = assignee.get("accountId")
    reporter_id = reporter.get("accountId")
    responsible_id = responsible.get("accountId") if isinstance(responsible, dict) else None

    owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
    if owner_id is None:
        return

    key = issue["key"]
    cand_key = (key, role)
    if cand_key in by_key_role:
        return

    sprint_num, sprint_name = extract_max_sprint_number(f.get(cfg.sprint_field))

    orig_sec = f.get("timeoriginalestimate")
    orig_hours = round(orig_sec / 3600, 1) if orig_sec else None

    h_analyst = f.get(cfg.role_hours_fields.get("analyst", ""))
    h_tester = f.get(cfg.role_hours_fields.get("tester", ""))
    h_developer = f.get(cfg.role_hours_fields.get("developer", ""))

    # formal_only — только для аналитика и только когда не assignee
    formal_only = False
    if role == "analyst" and assignee_id not in role_team:
        formal_only = not h_analyst and not h_tester

    hours = estimate_hours_for_role(f, role, bucket, status_name, cfg, sp_field)

    by_key_role[cand_key] = {
        "key": key,
        "url": f"{base_url}/browse/{key}",
        "summary": f.get("summary") or "",
        "status_name": status_name,
        "bucket": bucket,
        "role": role,
        "owner_id": owner_id,
        "owner_file_name": role_team[owner_id]["file_name"],
        "hours": hours,
        "board": source_label,
        "sprint_num": sprint_num,
        "sprint_name": sprint_name,
        "formal_only": formal_only,
        "is_pseudo": False,
        "hours_analyst": h_analyst,
        "hours_tester": h_tester,
        "hours_developer": h_developer,
        "hours_original": orig_hours,
    }
    counters["matched"] += 1


def _add_pseudo_tasks(cfg: SprintConfig, target_sprint_num: int | None) -> list[dict]:
    """Сформировать список псевдо-задач для конкретного целевого спринта.

    Правила попадания:
      target_sprint_num задачи == target_sprint_num спринта  → попадает (разовая)
      target_sprint_num задачи is None и recurring=True       → попадает (постоянная)
      иначе → не попадает

    Плюс — авто-добавление "Руководство" для лидов (всегда recurring).
    """
    items = []

    # Карта member_id → member info
    members_by_id: dict[int, dict] = {}
    for acc_id, info in cfg.team.items():
        mid = info.get("id")
        if mid is not None:
            members_by_id[mid] = {"account_id": acc_id, **info}

    # 1) Явные псевдо-задачи из конфига — с учётом target_sprint_num и recurring
    for pt in cfg.pseudo_tasks:
        target = pt.get("target_sprint_num")
        recurring = pt.get("recurring", False)

        # Решаем — попадает ли в этот спринт
        applies = False
        if target is not None and target == target_sprint_num:
            applies = True
        elif target is None and recurring:
            applies = True

        if not applies:
            continue

        mid = pt["member_id"]
        member = members_by_id.get(mid)
        if not member:
            continue
        items.append({
            "key": f"pseudo:{mid}:{pt['name']}",
            "url": "",
            "summary": pt["name"],
            "status_name": "",
            "bucket": pt["bucket"],
            "role": member["role"],
            "owner_id": member["account_id"],
            "owner_file_name": member["file_name"],
            "hours": pt["hours"],
            "board": "(псевдо)",
            "sprint_num": None,
            "sprint_name": None,
            "formal_only": False,
            "is_pseudo": True,
            "hours_analyst": None,
            "hours_tester": None,
            "hours_developer": None,
            "hours_original": None,
        })

    # 2) "Руководство" — для каждого лида среди enabled-ролей
    if cfg.leader_management_enabled and cfg.leader_hours > 0:
        lead_role_names = {r["name"] for r in cfg.roles if r["is_lead"] and r["enabled"]}
        for acc_id, info in cfg.team.items():
            if info.get("role") not in lead_role_names:
                continue
            items.append({
                "key": f"pseudo:mgmt:{info.get('id')}",
                "url": "",
                "summary": "Руководство",
                "status_name": "",
                "bucket": "Руководство",
                "role": info["role"],
                "owner_id": acc_id,
                "owner_file_name": info["file_name"],
                "hours": cfg.leader_hours,
                "board": "(псевдо)",
                "sprint_num": None,
                "sprint_name": None,
                "formal_only": False,
                "is_pseudo": True,
                "hours_analyst": None,
                "hours_tester": None,
                "hours_developer": None,
                "hours_original": None,
            })

    return items


def collect_candidates(client: JiraClient, cfg: SprintConfig) -> tuple[list[dict], dict]:
    """Собрать кандидатов для всех включённых ролей.

    Возвращает (список_кандидатов, диагностика).
    Одна Jira-задача может породить несколько кандидатов (по одному на каждую
    подходящую роль).
    Псевдо-задачи НЕ включаются — они добавляются в allocate.
    """
    sp_field = find_story_points_field(client)
    fields_param = _build_fields_param(cfg, sp_field)
    base_url = client.base_url

    # Индекс: status → [(role, bucket), ...] только для enabled
    status_to_roles = _enabled_roles_by_status(cfg)
    # Кэш: role → team членов этой роли
    team_by_role: dict[str, dict[str, dict]] = {}
    for r in cfg.roles:
        if r["enabled"]:
            team_by_role[r["name"]] = _team_with_role(cfg, r["name"])

    by_key_role: dict[tuple[str, str], dict] = {}
    diagnostics: dict[str, Any] = {
        "sp_field": sp_field,
        "by_source": [],
        "enabled_roles": [r["name"] for r in cfg.roles if r["enabled"]],
    }

    def process_issues(issues: list[dict], source_label: str, source_kind: str):
        counters = {"matched": 0, "skipped_epic": 0}
        for it in issues:
            status_name = it["fields"]["status"]["name"]
            role_buckets = status_to_roles.get(status_name, [])
            if not role_buckets:
                continue
            for role, bucket in role_buckets:
                _process_issue_for_role(
                    it, role, bucket, team_by_role.get(role, {}),
                    source_label, by_key_role, counters,
                    cfg, base_url, sp_field,
                )
        diagnostics["by_source"].append({
            "source": source_label, "kind": source_kind,
            "fetched": len(issues), **counters,
        })

    for board_name, board_id in cfg.boards.items():
        try:
            issues = fetch_board_issues(client, board_id, fields_param)
        except Exception as e:
            diagnostics["by_source"].append({
                "source": board_name, "kind": "board", "error": str(e),
            })
            continue
        process_issues(issues, board_name, "board")

    for component_name in cfg.extra_components:
        try:
            issues = fetch_component_issues(client, cfg.project_key, component_name, fields_param)
        except Exception as e:
            diagnostics["by_source"].append({
                "source": component_name, "kind": "component", "error": str(e),
            })
            continue
        process_issues(issues, f"component:{component_name}", "component")

    return list(by_key_role.values()), diagnostics


# -------------------- Сортировка и приоритеты --------------------

def _is_estimated(task: dict, cfg: SprintConfig) -> bool:
    """Оцененная — заполнено поле часов для роли по бакету.

    Используется как один из ключей сортировки.
    """
    if task.get("is_pseudo"):
        return True  # псевдо у нас всегда "оценены"
    bucket = task["bucket"]
    role_for_field = _BUCKET_TO_ROLE_HOURS_FIELD.get(bucket)
    if role_for_field == "analyst":
        return bool(task.get("hours_analyst"))
    if role_for_field == "tester":
        return bool(task.get("hours_tester"))
    if role_for_field == "designer":
        # У дизайнера нет своего поля сейчас — fallback на любую заполненную
        return bool(task.get("hours_original"))
    if role_for_field == "developer":
        return bool(task.get("hours_developer"))
    return False


def _sort_key(task: dict, cfg: SprintConfig):
    """Ключ сортировки кандидатов внутри владельца."""
    return (
        # Псевдо-задачи всегда первыми
        0 if task.get("is_pseudo") else 1,
        # Дальше — есть ли спринт
        0 if task.get("sprint_num") is not None else 1,
        -(task.get("sprint_num") or 0),
        # Оценённые раньше
        0 if _is_estimated(task, cfg) else 1,
        # Приоритет статуса (псевдо — пусто, идёт в конец)
        cfg.status_priority.get(task["status_name"], 99),
        # Крупные раньше
        -task["hours"],
    )


def compute_priorities(candidates: list[dict], cfg: SprintConfig) -> None:
    """Проставить task['priority'] = 1..N в разрезе (владелец, роль).

    formal_only задачи приоритет не получают.
    """
    by_owner_role: dict[tuple[str, str], list[dict]] = {}
    for t in candidates:
        key = (t["owner_id"], t["role"])
        by_owner_role.setdefault(key, []).append(t)

    for tasks in by_owner_role.values():
        non_formal = [t for t in tasks if not t.get("formal_only")]
        non_formal.sort(key=lambda x: _sort_key(x, cfg))
        for i, t in enumerate(non_formal, start=1):
            t["priority"] = i
        for t in tasks:
            if t.get("formal_only"):
                t["priority"] = None


# -------------------- allocate --------------------

def allocate(candidates: list[dict], cfg: SprintConfig,
              target_sprint_num: int | None = None) -> tuple[list[dict], list[dict], dict]:
    """Распределение задач до бюджета на каждого человека.

    target_sprint_num — номер целевого спринта; нужен, чтобы фильтровать
    разовые псевдо-задачи (с target_sprint_num) от постоянных (recurring).
    Если не передан — берутся только recurring + автодобавление "Руководство".

    Псевдо-задачи (отпуска, руководство) кладутся в спринт первыми
    и уменьшают остаток бюджета.

    formal_only задачи в спринт не идут.

    Возвращает (allocated, overflow, used_by_owner).
    """
    pseudo = _add_pseudo_tasks(cfg, target_sprint_num)
    real = [c for c in candidates if not c.get("formal_only")]

    # Сортируем — псевдо уже наверху благодаря _sort_key
    everything = pseudo + real
    everything.sort(key=lambda x: _sort_key(x, cfg))

    allocated: list[dict] = []
    used: dict[str, float] = {acc_id: 0.0 for acc_id in cfg.team}
    remaining: list[dict] = []

    budget = cfg.hours_per_person

    # Проход 1: целые задачи (включая псевдо — они идут первыми по сортировке)
    for task in everything:
        owner = task["owner_id"]
        if owner not in used:
            # Владельца нет в текущем team (странно, но возможно при ручных правках)
            continue
        if used[owner] + task["hours"] <= budget:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            remaining.append(task)

    # Проход 2: добор мелкими целиком
    remaining.sort(key=lambda t: t["hours"])
    rest2 = []
    for task in remaining:
        owner = task["owner_id"]
        if used[owner] + task["hours"] <= budget:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            rest2.append(task)

    # Проход 3: режем последнюю задачу до точного остатка
    overflow = []
    sliced_owners: set[str] = set()
    for task in rest2:
        owner = task["owner_id"]
        gap = budget - used[owner]
        if gap > 0 and owner not in sliced_owners and not task.get("is_pseudo"):
            partial = task.copy()
            partial["hours"] = round(gap, 1)
            partial["partial_from"] = task["hours"]
            used[owner] = budget
            sliced_owners.add(owner)
            allocated.append(partial)
        else:
            overflow.append(task)

    return allocated, overflow, used
