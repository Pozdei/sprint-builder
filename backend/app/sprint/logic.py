"""Бизнес-логика формирования спринта — фаза 2.11 (направления задач).

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
              "timeoriginalestimate", "issuetype", "labels"]
    if sp_field:
        fields.append(sp_field)
    fields.extend(cfg.role_hours_fields.values())
    fields.append(cfg.sprint_field)
    fields.append(cfg.responsible_field)
    if cfg.developer_field:
        fields.append(cfg.developer_field)
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

def _positive_float(v: Any) -> float | None:
    """float(v), если получилось и значение > 0, иначе None. Глотает мусор (None, "", текст)."""
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    return fv if fv > 0 else None


# Маппинг бакета → категория поля часов в Jira.
_BUCKET_TO_ROLE_HOURS_FIELD = {
    "Анализ":       "analyst",
    "Тестирование": "tester",
    "Дизайн":       "designer",
    "Разработка":   "developer",
}

# Бакеты ревью: время определяется только настроенным дефолтом (role_status_default_hours),
# никакие поля задачи (timeoriginalestimate, sp, hours_developer) не учитываются.
_REVIEW_BUCKETS = {"Код-ревью", "Дизайн-ревью"}

# Маппинг вида работы → роль + бакет
_WORK_TYPE_INFO: dict[str, dict[str, str]] = {
    "analytics":     {"role": "analyst",        "bucket": "Анализ"},
    "development":   {"role": "developer",       "bucket": "Разработка"},
    "testing":       {"role": "analyst",         "bucket": "Тестирование"},
    "design":        {"role": "designer",        "bucket": "Дизайн"},
    "code_review":   {"role": "developer_lead",  "bucket": "Код-ревью"},
    "design_review": {"role": "designer_lead",   "bucket": "Дизайн-ревью"},
}

# Виды работ, которые порождаются ПОСЛЕ аллокации (когда знаем, что задача выполнится)
_POST_ALLOC_WORK_TYPES = {"testing", "code_review", "design_review"}


def _default_hours_for(cfg: SprintConfig, role: str, status_name: str) -> float:
    """Дефолтные часы для пары (роль, статус). Fallback — global default."""
    for item in cfg.role_status_default_hours:
        if item["role"] == role and item["jira_status"] == status_name:
            return item["hours"]
    # Для developer_frontend / developer_backend — fallback на developer
    if "_" in role and role.startswith("developer"):
        for item in cfg.role_status_default_hours:
            if item["role"] == "developer" and item["jira_status"] == status_name:
                return item["hours"]
    return cfg.default_task_hours


def estimate_hours_for_role(fields: dict, role: str, bucket: str,
                             status_name: str, cfg: SprintConfig,
                             sp_field: str | None) -> float:
    """Оценка часов задачи в контексте конкретной роли и бакета.

    Приоритет:
    1) Поле часов соответствующей «категории» в Jira (analyst/tester/designer/developer).
    2) timeoriginalestimate.
    3) Story Points × 4.
    4) Дефолт для пары (роль, статус) либо общий default_task_hours.

    Для ревью-бакетов (Код-ревью, Дизайн-ревью) шаги 1–3 пропускаются:
    время ревью не зависит от оценки разработки — только дефолт из настроек.
    """
    if bucket in _REVIEW_BUCKETS:
        # Ищем дефолт по имени бакета (= Jira-статус ревью в настройках),
        # а не по текущему статусу задачи — он не релевантен для генерируемых шагов
        return _default_hours_for(cfg, role, bucket)

    hours_role = _BUCKET_TO_ROLE_HOURS_FIELD.get(bucket)
    if hours_role:
        field_id = cfg.role_hours_fields.get(hours_role)
        if field_id:
            fv = _positive_float(fields.get(field_id))
            if fv is not None:
                return fv

    sec = fields.get("timeoriginalestimate")
    if sec:
        return round(sec / 3600, 1)

    if sp_field:
        sp = fields.get(sp_field)
        if sp:
            try:
                return float(sp) * 4
            except (TypeError, ValueError):
                pass

    return _default_hours_for(cfg, role, status_name)


# -------------------- Направления задач --------------------

def _find_direction(labels: list[str], cfg: SprintConfig) -> dict | None:
    """Найти первое направление, чьи метки пересекаются с метками задачи."""
    if not cfg.directions or not labels:
        return None
    label_set = {l.lower() for l in labels}
    for direction in cfg.directions:
        dir_labels = {l.lower() for l in direction.get("labels", [])}
        if dir_labels & label_set:
            return direction
    return None


def _find_pipeline_position(status_name: str, work_types: list[str],
                             cfg: SprintConfig) -> int:
    """Позиция текущего статуса в pipeline направления (0-based).

    Ищем первый work_type, чей бакет содержит данный статус в role_status_buckets.
    Если не нашли — возвращаем -1 (позиция неизвестна, дополнительные кандидаты
    не генерируем).
    """
    bucket_statuses: dict[str, set] = {}
    for item in cfg.role_status_buckets:
        bucket_statuses.setdefault(item["bucket"], set()).add(item["jira_status"])

    for pos, wt in enumerate(work_types):
        info = _WORK_TYPE_INFO.get(wt)
        if not info:
            continue
        if status_name in bucket_statuses.get(info["bucket"], set()):
            return pos
    return -1


def _find_lead_owner(cfg: SprintConfig,
                     lead_role: str) -> tuple[str, dict] | None:
    """Первый включённый лид заданной роли. Возвращает (account_id, info) или None."""
    lead_names = {
        r["name"] for r in cfg.roles
        if r.get("is_lead") and r.get("enabled") and r["name"] == lead_role
    }
    if not lead_names:
        return None
    for acc_id, info in cfg.team.items():
        if info.get("role") in lead_names:
            return acc_id, info
    return None


# -------------------- Сборка кандидатов --------------------

def _team_with_role(cfg: SprintConfig, role: str) -> dict[str, dict]:
    return {
        acc_id: info
        for acc_id, info in cfg.team.items()
        if info.get("role") == role
    }


def _enabled_roles_by_status(cfg: SprintConfig) -> dict[str, list[tuple[str, str]]]:
    """Индекс: status → [(role, bucket), ...] только для enabled-ролей."""
    enabled = {r["name"] for r in cfg.roles if r["enabled"]}
    index: dict[str, list[tuple[str, str]]] = {}
    for item in cfg.role_status_buckets:
        if item["role"] not in enabled:
            continue
        index.setdefault(item["jira_status"], []).append((item["role"], item["bucket"]))
    return index


def _is_content_role(role: str) -> bool:
    """True для «аналитических» ролей (аналитик, тестер, QA и т.д.).

    Такие роли используют цепочку assignee → responsible → reporter
    при поиске владельца задачи. Технические роли (developer*, designer*)
    берут только assignee.
    """
    return not (role.startswith("developer") or role.startswith("designer"))


def _resolve_owner(role: str, assignee_id: str | None,
                    responsible_id: str | None, reporter_id: str | None,
                    role_team: dict[str, dict]) -> str | None:
    """Владелец задачи для роли.

    - Аналитические роли (analyst, qa, tester и кастомные):
      assignee → responsible → reporter.
    - Технические роли (developer*, designer*): только assignee.
    """
    if assignee_id and assignee_id in role_team:
        return assignee_id

    if _is_content_role(role):
        if responsible_id and responsible_id in role_team:
            return responsible_id
        if reporter_id and reporter_id in role_team:
            return reporter_id
    return None


def _extract_owners(f: dict, cfg: SprintConfig) -> tuple[str | None, str | None, str | None]:
    """(assignee_id, reporter_id, responsible_id) из полей Jira-задачи."""
    assignee_id = (f.get("assignee") or {}).get("accountId")
    reporter_id = (f.get("reporter") or {}).get("accountId")
    responsible = f.get(cfg.responsible_field) or {}
    responsible_id = responsible.get("accountId") if isinstance(responsible, dict) else None
    return assignee_id, reporter_id, responsible_id


def _extract_role_hours(f: dict, cfg: SprintConfig) -> tuple:
    """(hours_analyst, hours_tester, hours_developer, hours_original) из полей Jira-задачи."""
    h_analyst = f.get(cfg.role_hours_fields.get("analyst", ""))
    h_tester = f.get(cfg.role_hours_fields.get("tester", ""))
    h_developer = f.get(cfg.role_hours_fields.get("developer", ""))
    orig_sec = f.get("timeoriginalestimate")
    orig_hours = round(orig_sec / 3600, 1) if orig_sec else None
    return h_analyst, h_tester, h_developer, orig_hours


def _has_real_estimate(f: dict, bucket: str, cfg: SprintConfig,
                        sp_field: str | None) -> bool:
    """True если у задачи есть хоть одна явная оценка (не дефолт).

    Для ревью-бакетов всегда True: их часы задаются настроенным дефолтом,
    а не «заглушкой» — подсвечивать нечего.
    """
    if bucket in _REVIEW_BUCKETS:
        return True

    hours_role = _BUCKET_TO_ROLE_HOURS_FIELD.get(bucket)
    if hours_role:
        field_id = cfg.role_hours_fields.get(hours_role)
        if field_id and _positive_float(f.get(field_id)) is not None:
            return True
    if f.get("timeoriginalestimate"):
        return True
    if sp_field and f.get(sp_field):
        return True
    return False


def _extract_developer_name(f: dict, cfg: SprintConfig) -> str | None:
    """Имя разработчика из поля developer_field: сначала file_name из команды, потом displayName из Jira."""
    if not cfg.developer_field:
        return None
    dev_val = f.get(cfg.developer_field) or {}
    if not isinstance(dev_val, dict):
        return None
    acc_id = dev_val.get("accountId")
    if acc_id and acc_id in cfg.team:
        return cfg.team[acc_id]["file_name"]
    return dev_val.get("displayName") or None


def _make_candidate(
    f: dict, cfg: SprintConfig, base_url: str, sp_field: str | None,
    *, key: str, role: str, bucket: str, owner_id: str, owner_file_name: str,
    status_name: str, board: str, direction: str | None, labels: list,
    formal_only: bool = False,
) -> dict:
    """Собрать словарь-кандидата из полей Jira-задачи.

    Единая точка формирования структуры кандидата — используется и для обычных
    кандидатов (role_status_buckets), и для pre-allocation шагов pipeline.
    """
    assignee_id, reporter_id, responsible_id = _extract_owners(f, cfg)
    sprint_num, sprint_name = extract_max_sprint_number(f.get(cfg.sprint_field))
    h_analyst, h_tester, h_developer, orig_hours = _extract_role_hours(f, cfg)
    return {
        "key": key,
        "url": f"{base_url}/browse/{key}",
        "summary": f.get("summary") or "",
        "status_name": status_name,
        "bucket": bucket,
        "role": role,
        "owner_id": owner_id,
        "owner_file_name": owner_file_name,
        "hours": estimate_hours_for_role(f, role, bucket, status_name, cfg, sp_field),
        "hours_is_default": not _has_real_estimate(f, bucket, cfg, sp_field),
        "board": board,
        "sprint_num": sprint_num,
        "sprint_name": sprint_name,
        "formal_only": formal_only,
        "is_pseudo": False,
        "hours_analyst": h_analyst,
        "hours_tester": h_tester,
        "hours_developer": h_developer,
        "hours_original": orig_hours,
        "direction": direction,
        "labels": labels,
        "responsible_id": responsible_id,
        "assignee_id": assignee_id,
        "reporter_id": reporter_id,
        "developer_name": _extract_developer_name(f, cfg),
    }


def _process_issue_for_role(
    issue: dict, role: str, bucket: str, role_team: dict[str, dict],
    source_label: str, by_key_role: dict, counters: dict,
    cfg: SprintConfig, base_url: str, sp_field: str | None,
    direction_name: str | None = None,
    labels: list | None = None,
) -> None:
    """Обработать одну задачу в контексте одной роли.

    Ключ by_key_role — (jira_key, role, bucket), чтобы один аналитик мог иметь
    одновременно «Анализ» и «Тестирование» по одной задаче.
    """
    f = issue["fields"]

    issuetype = (f.get("issuetype") or {}).get("name", "")
    if issuetype.lower() in ("эпик", "epic"):
        counters["skipped_epic"] += 1
        return

    status_name = f["status"]["name"]
    assignee_id, reporter_id, responsible_id = _extract_owners(f, cfg)

    owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
    if owner_id is None:
        return

    key = issue["key"]
    cand_key = (key, role, bucket)
    if cand_key in by_key_role:
        return

    formal_only = False
    if role == "analyst" and assignee_id not in role_team:
        h_analyst, h_tester, _, _ = _extract_role_hours(f, cfg)
        formal_only = not h_analyst and not h_tester

    by_key_role[cand_key] = _make_candidate(
        f, cfg, base_url, sp_field,
        key=key, role=role, bucket=bucket, owner_id=owner_id,
        owner_file_name=role_team[owner_id]["file_name"],
        status_name=status_name, board=source_label,
        direction=direction_name, labels=labels or [],
        formal_only=formal_only,
    )
    counters["matched"] += 1


def _resolve_designer_for_direction(
    direction: dict, cfg: SprintConfig,
    team_by_role: dict[str, dict[str, dict]],
    assignee_id: str | None,
) -> tuple[str | None, dict[str, dict]]:
    """Определить владельца шага дизайна для задачи из направления.

    Порядок:
    1. Assignee, если он в команде с ролью designer.
    2. direction["designer_id"] — явно выбранный в настройках направления.
    3. Единственный/первый в команде с ролью designer.
    """
    role_team = team_by_role.get("designer") or _team_with_role(cfg, "designer")

    if assignee_id and assignee_id in role_team:
        return assignee_id, role_team

    designer_id = (direction.get("designer_id") or "").strip()
    if designer_id and designer_id in role_team:
        return designer_id, role_team

    if role_team:
        return next(iter(role_team)), role_team

    return None, role_team


def _resolve_developer_for_direction(
    f: dict, direction: dict, cfg: SprintConfig,
    team_by_role: dict[str, dict[str, dict]],
    assignee_id: str | None,
) -> tuple[str | None, str | None, dict[str, dict]]:
    """Определить владельца шага разработки для задачи из направления.

    Порядок:
    1. Поле «Разработчик» (developer_field) — ищем среди ВСЕЙ команды, берём с его фактической ролью.
    2. Assignee, если он в команде нужной dev_role.
    3. Автовыбор первого из dev_role.

    Возвращает (owner_id, actual_role, role_team).
    """
    dev_role = direction.get("dev_role") or "developer"
    role_team = team_by_role.get(dev_role) or _team_with_role(cfg, dev_role)

    # 1. Поле «Разработчик» из Jira — безусловный приоритет.
    #    Если поле явно заполнено — берём этого человека, не проверяя соответствие dev_role.
    if cfg.developer_field:
        dev_field_val = f.get(cfg.developer_field) or {}
        dev_field_id = dev_field_val.get("accountId") if isinstance(dev_field_val, dict) else None
        if dev_field_id:
            if dev_field_id in cfg.team:
                person_role = cfg.team[dev_field_id].get("role", dev_role)
                actual_team = team_by_role.get(person_role) or _team_with_role(cfg, person_role)
                return dev_field_id, person_role, actual_team
            else:
                # Не в команде конфига — синтетическая запись с displayName из Jira.
                display_name = dev_field_val.get("displayName") or dev_field_id
                synth_team = {dev_field_id: {"file_name": display_name, "role": dev_role, "salary": 0}}
                return dev_field_id, dev_role, synth_team

    # 2. Assignee в команде нужной dev_role
    if assignee_id and assignee_id in role_team:
        return assignee_id, dev_role, role_team

    # 3. Автовыбор из команды
    if role_team:
        first_id = next(iter(role_team))
        return first_id, dev_role, role_team

    return None, dev_role, role_team


def _generate_direction_pre_candidates(
    issue: dict, status_name: str, direction: dict,
    labels: list, by_key_role: dict, cfg: SprintConfig,
    base_url: str, sp_field: str | None, counters: dict,
    team_by_role: dict[str, dict[str, dict]],
) -> None:
    """Для задачи направления создать кандидатов по будущим шагам pipeline.

    Генерируем только шаги ПОСЛЕ текущей позиции статуса в pipeline,
    и только те, что НЕ являются post-allocation (testing/code_review/design_review).
    Последние порождаются уже после аллокации.

    Для шага «development» разработчик определяется через _resolve_developer_for_direction:
      - Поле Jira «Разработчик» (developer_field) → приоритет
      - Иначе: единственный/первый разработчик направления (dev_role)
    Если задача уже В разработке — этот путь не вызывается (обрабатывается role_status_buckets).
    """
    f = issue["fields"]
    key = issue["key"]
    work_types = direction.get("work_types", [])

    current_pos = _find_pipeline_position(status_name, work_types, cfg)
    if current_pos < 0:
        return  # Статус не распознан в pipeline — не генерируем

    assignee_id, reporter_id, responsible_id = _extract_owners(f, cfg)

    for pos, wt in enumerate(work_types):
        if pos <= current_pos:
            continue  # уже в этой или более ранней стадии — пропускаем
        if wt in _POST_ALLOC_WORK_TYPES:
            continue  # генерируется post-allocation

        info = _WORK_TYPE_INFO.get(wt)
        if not info:
            continue

        bucket = info["bucket"]

        if wt == "development":
            owner_id, role, role_team = _resolve_developer_for_direction(
                f, direction, cfg, team_by_role, assignee_id,
            )
        elif wt == "design":
            role = "designer"
            owner_id, role_team = _resolve_designer_for_direction(
                direction, cfg, team_by_role, assignee_id,
            )
        elif wt == "testing":
            role = direction.get("tester_role") or "analyst"
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
        elif wt == "analytics":
            role = direction.get("analyst_role") or "analyst"
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
        else:
            role = info["role"]
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)

        if owner_id is None:
            continue

        cand_key = (key, role, bucket)
        if cand_key in by_key_role:
            continue

        by_key_role[cand_key] = _make_candidate(
            f, cfg, base_url, sp_field,
            key=key, role=role, bucket=bucket, owner_id=owner_id,
            owner_file_name=role_team[owner_id]["file_name"],
            status_name=status_name, board=f"[{direction['name']}]",
            direction=direction["name"], labels=labels,
        )
        counters["matched"] += 1


def _add_pseudo_tasks(cfg: SprintConfig, target_sprint_num: int | None) -> list[dict]:
    """Сформировать список псевдо-задач для конкретного целевого спринта."""
    items = []

    members_by_id: dict[int, dict] = {}
    for acc_id, info in cfg.team.items():
        mid = info.get("id")
        if mid is not None:
            members_by_id[mid] = {"account_id": acc_id, **info}

    for pt in cfg.pseudo_tasks:
        target = pt.get("target_sprint_num")
        recurring = pt.get("recurring", False)

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
            "direction": None,
            "labels": [],
            "responsible_id": None,
            "assignee_id": None,
            "reporter_id": None,
        })

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
                "direction": None,
                "labels": [],
                "responsible_id": None,
                "assignee_id": None,
                "reporter_id": None,
            })

    return items


def collect_candidates(client: JiraClient, cfg: SprintConfig) -> tuple[list[dict], dict]:
    """Собрать кандидатов для всех включённых ролей + direction-pipeline кандидатов.

    Одна Jira-задача может породить несколько кандидатов:
    - По одному на каждую (роль, бакет) из role_status_buckets.
    - Дополнительно: по каждому «будущему» шагу pipeline, если у задачи есть направление.
    """
    sp_field = find_story_points_field(client)
    fields_param = _build_fields_param(cfg, sp_field)
    base_url = client.base_url

    status_to_roles = _enabled_roles_by_status(cfg)
    team_by_role: dict[str, dict[str, dict]] = {}
    for r in cfg.roles:
        if r["enabled"]:
            team_by_role[r["name"]] = _team_with_role(cfg, r["name"])

    by_key_role: dict[tuple[str, str, str], dict] = {}
    diagnostics: dict[str, Any] = {
        "sp_field": sp_field,
        "by_source": [],
        "enabled_roles": [r["name"] for r in cfg.roles if r["enabled"]],
    }

    def process_issues(issues: list[dict], source_label: str, source_kind: str):
        counters = {"matched": 0, "skipped_epic": 0}
        for it in issues:
            f = it["fields"]
            issuetype = (f.get("issuetype") or {}).get("name", "")
            if issuetype.lower() in ("эпик", "epic"):
                counters["skipped_epic"] += 1
                continue

            status_name = f["status"]["name"]
            labels = f.get("labels") or []
            direction = _find_direction(labels, cfg)
            direction_name = direction["name"] if direction else None

            # Стандартные кандидаты по role_status_buckets
            role_buckets = status_to_roles.get(status_name, [])
            direction_dev_role = (direction.get("dev_role") or "developer") if direction else None
            for role, bucket in role_buckets:
                # Для бакета «Разработка»: если у задачи есть направление с dev_role,
                # пропускаем роли разработчика, не совпадающие с dev_role направления.
                if direction and bucket == "Разработка" and direction_dev_role and role != direction_dev_role:
                    continue
                _process_issue_for_role(
                    it, role, bucket, team_by_role.get(role, {}),
                    source_label, by_key_role, counters,
                    cfg, base_url, sp_field,
                    direction_name=direction_name,
                    labels=labels,
                )

            # Дополнительные pre-allocation кандидаты по pipeline направления.
            # Вызываем НЕЗАВИСИМО от role_buckets — position check внутри вернёт -1
            # если статус не в role_status_buckets и тогда ничего не генерируем.
            if direction:
                _generate_direction_pre_candidates(
                    it, status_name, direction, labels,
                    by_key_role, cfg, base_url, sp_field, counters,
                    team_by_role,
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
    if task.get("is_pseudo"):
        return True
    bucket = task["bucket"]
    role_for_field = _BUCKET_TO_ROLE_HOURS_FIELD.get(bucket)
    if role_for_field == "analyst":
        return bool(task.get("hours_analyst"))
    if role_for_field == "tester":
        return bool(task.get("hours_tester"))
    if role_for_field == "designer":
        return bool(task.get("hours_original"))
    if role_for_field == "developer":
        return bool(task.get("hours_developer"))
    return False


def _sort_key(task: dict, cfg: SprintConfig):
    return (
        0 if task.get("is_pseudo") else 1,
        0 if task.get("sprint_num") is not None else 1,
        -(task.get("sprint_num") or 0),
        0 if _is_estimated(task, cfg) else 1,
        cfg.status_priority.get(task["status_name"], 99),
        -task["hours"],
    )


def compute_priorities(candidates: list[dict], cfg: SprintConfig) -> None:
    """Проставить task['priority'] = 1..N в разрезе (владелец, роль)."""
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
    """Распределение задач до бюджета на каждого человека."""
    pseudo = _add_pseudo_tasks(cfg, target_sprint_num)
    real = [c for c in candidates if not c.get("formal_only")]

    everything = pseudo + real
    everything.sort(key=lambda x: _sort_key(x, cfg))

    allocated: list[dict] = []
    used: dict[str, float] = {acc_id: 0.0 for acc_id in cfg.team}
    remaining: list[dict] = []

    budget = cfg.hours_per_person

    for task in everything:
        owner = task["owner_id"]
        if owner not in used:
            continue
        if used[owner] + task["hours"] <= budget:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            remaining.append(task)

    remaining.sort(key=lambda t: t["hours"])
    rest2 = []
    for task in remaining:
        owner = task["owner_id"]
        if used[owner] + task["hours"] <= budget:
            used[owner] += task["hours"]
            allocated.append(task)
        else:
            rest2.append(task)

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

    for task in overflow:
        owner = task["owner_id"]
        remaining = round(budget - used.get(owner, 0), 1)
        task_hours = task.get("hours", 0)
        if remaining <= 0:
            task["overflow_reason"] = "Бюджет исчерпан"
        elif task_hours > remaining:
            task["overflow_reason"] = f"Нужно {task_hours} ч, доступно {remaining} ч"
        else:
            task["overflow_reason"] = "Низкий приоритет"

    return allocated, overflow, used


# -------------------- Ожидаемый итог спринта --------------------

def compute_sprint_expected_results(
    allocated: list[dict], cfg: SprintConfig,
) -> dict[str, str]:
    """Вычислить ожидаемый итог спринта для каждого уникального ключа задачи.

    Алгоритм:
    - Группируем все аллоцированные не-псевдо строки по ключу Jira.
    - Для каждого ключа сортируем бакеты по порядку pipeline направления
      (или дефолтному порядку если направления нет).
    - Последний бакет = на каком этапе окажется задача к концу спринта.
    - Если последний шаг — финальный в pipeline И не урезан (partial_from=None)
      → возвращаем терминальный статус (первый из cfg.terminal_statuses).
    """
    direction_by_name = {d["name"]: d for d in cfg.directions}
    terminal = cfg.terminal_statuses[0] if cfg.terminal_statuses else "Выполнено"

    # Дефолтный порядок бакетов (без явного направления)
    _DEFAULT_BUCKET_ORDER = [
        "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование",
    ]

    # Группируем: key → список (bucket, is_partial)
    by_key: dict[str, list[tuple[str, bool]]] = {}
    key_direction: dict[str, str | None] = {}

    for task in allocated:
        if task.get("is_pseudo"):
            continue
        key = task["key"]
        by_key.setdefault(key, []).append(
            (task["bucket"], task.get("partial_from") is not None)
        )
        key_direction.setdefault(key, task.get("direction"))

    result: dict[str, str] = {}

    for key, steps in by_key.items():
        direction_name = key_direction.get(key)
        direction = direction_by_name.get(direction_name) if direction_name else None

        if direction:
            ordered_buckets = [
                _WORK_TYPE_INFO.get(wt, {}).get("bucket", wt)
                for wt in direction.get("work_types", [])
                if wt in _WORK_TYPE_INFO
            ]
        else:
            ordered_buckets = _DEFAULT_BUCKET_ORDER

        def _rank(bp: tuple[str, bool]) -> int:
            b, _ = bp
            try:
                return ordered_buckets.index(b)
            except ValueError:
                return len(ordered_buckets)

        sorted_steps = sorted(steps, key=_rank)
        if not sorted_steps:
            continue

        last_bucket, last_partial = sorted_steps[-1]
        is_final = bool(ordered_buckets) and last_bucket == ordered_buckets[-1]

        if is_final and not last_partial:
            result[key] = terminal
        elif not last_partial and ordered_buckets:
            # Шаг завершён, но не финальный — ожидаемый итог: следующий шаг
            try:
                idx = ordered_buckets.index(last_bucket)
                result[key] = ordered_buckets[idx + 1] if idx + 1 < len(ordered_buckets) else terminal
            except ValueError:
                result[key] = last_bucket
        else:
            result[key] = last_bucket

    return result


# -------------------- Post-allocation: pipeline-derived tasks --------------------

def _tester_hours(task: dict, tester_role: str, cfg: SprintConfig) -> float:
    """Часы шага тестирования: поле hours_tester задачи, иначе дефолт (роль, статус)."""
    fv = _positive_float(task.get("hours_tester"))
    if fv is not None:
        return fv
    return _default_hours_for(cfg, tester_role, task["status_name"])


def derive_pipeline_tasks(
    allocated: list[dict], cfg: SprintConfig,
) -> list[dict]:
    """Породить задачи тестирования, код-ревью и дизайн-ревью из выполненных задач.

    Для каждой non-partial задачи разработчика (bucket=Разработка):
      - Если направление включает «testing» → добавить задачу тестирования аналитику.
      - Всегда → добавить задачу код-ревью лиду разработки.

    Для каждой non-partial задачи дизайнера (bucket=Дизайн):
      - Всегда → добавить задачу дизайн-ревью лиду дизайна.
    """
    derived: list[dict] = []
    direction_by_name = {d["name"]: d for d in cfg.directions}

    # Множество уже существующих (key, role, bucket) в allocated — чтобы не дублировать
    allocated_keys: set[tuple] = {
        (t["key"], t["role"], t["bucket"])
        for t in allocated
        if not t.get("is_pseudo")
    }

    dev_lead    = _find_lead_owner(cfg, "developer_lead")
    design_lead = _find_lead_owner(cfg, "designer_lead")

    # Все роли разработчика из конфига направлений (developer, developer_frontend, ...)
    all_dev_roles: set[str] = {"developer"}
    for _d in cfg.directions:
        _dr = (_d.get("dev_role") or "").strip()
        if _dr:
            all_dev_roles.add(_dr)

    def _make_derived(base: dict, role: str, bucket: str,
                       owner_id: str, owner_file_name: str, hours: float) -> dict:
        t = base.copy()
        t.update({
            "bucket": bucket,
            "role": role,
            "owner_id": owner_id,
            "owner_file_name": owner_file_name,
            "hours": hours,
            "is_pseudo": False,
            "formal_only": False,
            "partial_from": None,
            "priority": None,
        })
        return t

    for task in allocated:
        if task.get("is_pseudo"):
            continue
        if task.get("partial_from") is not None:
            # Задача урезана — разработчик не закончит, тест/ревью не нужны
            continue

        key = task["key"]
        bucket = task["bucket"]
        direction_name = task.get("direction")
        direction = direction_by_name.get(direction_name) if direction_name else None
        work_types = direction.get("work_types", []) if direction else []

        # ---- Задача разработчика ----
        # Роль может быть "developer", "developer_frontend", "developer_backend" и т.д.
        # Проверяем по множеству ALL dev-ролей из конфига (не только из текущего direction),
        # чтобы ловить задачи без совпавшего direction.
        is_dev_task = bucket == "Разработка" and task.get("role") in all_dev_roles
        if is_dev_task:
            # Обходим post-allocation шаги в порядке pipeline направления.
            # Если направление не указано — дефолтный порядок: code_review → testing.
            post_alloc_order = [
                wt for wt in work_types if wt in _POST_ALLOC_WORK_TYPES
            ] or ["code_review", "testing"]

            for wt in post_alloc_order:
                if wt == "testing":
                    tester_role = (direction.get("tester_role") or "analyst") if direction else "analyst"
                    test_cand_key = (key, tester_role, "Тестирование")
                    if test_cand_key not in allocated_keys:
                        task_tester_id = (task.get("tester_id") or "").strip()
                        if task_tester_id and task_tester_id in cfg.team:
                            owner_id = task_tester_id
                            tester_team = {task_tester_id: cfg.team[task_tester_id]}
                        else:
                            tester_team = _team_with_role(cfg, tester_role)
                            owner_id = _resolve_owner(
                                tester_role,
                                task.get("assignee_id"),
                                task.get("responsible_id"),
                                task.get("reporter_id"),
                                tester_team,
                            )
                        if owner_id:
                            d = _make_derived(
                                task, tester_role, "Тестирование",
                                owner_id, tester_team[owner_id]["file_name"],
                                _tester_hours(task, tester_role, cfg),
                            )
                            derived.append(d)
                            allocated_keys.add(test_cand_key)

                elif wt == "code_review":
                    if dev_lead:
                        dev_lead_id, dev_lead_info = dev_lead
                        cr_cand_key = (key, "developer_lead", "Код-ревью")
                        if cr_cand_key not in allocated_keys:
                            hours = _default_hours_for(cfg, "developer_lead", "Код-ревью")
                            d = _make_derived(
                                task, "developer_lead", "Код-ревью",
                                dev_lead_id, dev_lead_info["file_name"], hours,
                            )
                            derived.append(d)
                            allocated_keys.add(cr_cand_key)

        # ---- Код-ревью завершено → тестирование ----
        elif bucket == "Код-ревью":
            if direction:
                cr_idx = next((i for i, wt in enumerate(work_types) if wt == "code_review"), -1)
                has_testing = cr_idx >= 0 and any(wt == "testing" for wt in work_types[cr_idx + 1:])
            else:
                has_testing = True

            if has_testing:
                tester_role = (direction.get("tester_role") or "analyst") if direction else "analyst"
                tester_team = _team_with_role(cfg, tester_role)
                test_cand_key = (key, tester_role, "Тестирование")
                if test_cand_key not in allocated_keys:
                    owner_id = _resolve_owner(
                        tester_role,
                        task.get("assignee_id"),
                        task.get("responsible_id"),
                        task.get("reporter_id"),
                        tester_team,
                    )
                    if owner_id:
                        d = _make_derived(
                            task, tester_role, "Тестирование",
                            owner_id, tester_team[owner_id]["file_name"],
                            _tester_hours(task, tester_role, cfg),
                        )
                        derived.append(d)
                        allocated_keys.add(test_cand_key)

        # ---- Задача дизайнера ----
        elif bucket == "Дизайн" and task.get("role") == "designer":
            post_alloc_order = [
                wt for wt in work_types if wt in _POST_ALLOC_WORK_TYPES
            ] or ["design_review"]

            for wt in post_alloc_order:
                if wt == "design_review" and design_lead:
                    design_lead_id, design_lead_info = design_lead
                    dr_cand_key = (key, "designer_lead", "Дизайн-ревью")
                    if dr_cand_key not in allocated_keys:
                        hours = _default_hours_for(cfg, "designer_lead", "Дизайн-ревью")
                        d = _make_derived(
                            task, "designer_lead", "Дизайн-ревью",
                            design_lead_id, design_lead_info["file_name"], hours,
                        )
                        derived.append(d)
                        allocated_keys.add(dr_cand_key)

    return derived
