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
    if cfg.designer_field:
        fields.append(cfg.designer_field)
    if cfg.tester_field:
        fields.append(cfg.tester_field)
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

# Бакеты ревью/вехи: время определяется только настроенным дефолтом
# (role_status_default_hours), никакие поля задачи (timeoriginalestimate, sp,
# hours_developer) не учитываются. «Релиз» — финальная веха пайплайна разработки.
_REVIEW_BUCKETS = {"Код-ревью", "Дизайн-ревью", "Релиз"}

# Маппинг вида работы → роль + бакет
_WORK_TYPE_INFO: dict[str, dict[str, str]] = {
    "analytics":     {"role": "analyst",        "bucket": "Анализ"},
    "development":   {"role": "developer",       "bucket": "Разработка"},
    "testing":       {"role": "analyst",         "bucket": "Тестирование"},
    "design":        {"role": "designer",        "bucket": "Дизайн"},
    "code_review":   {"role": "developer_lead",  "bucket": "Код-ревью"},
    "design_review": {"role": "designer_lead",   "bucket": "Дизайн-ревью"},
    "release":       {"role": "developer_lead",  "bucket": "Релиз"},
}

# Виды работ, которые порождаются ПОСЛЕ аллокации (когда знаем, что задача выполнится)
_POST_ALLOC_WORK_TYPES = {"testing", "code_review", "design_review", "release"}


def _role_override(direction: dict | None, work_type: str) -> str:
    """Роль направления для work_type, заданная пользователем вместо системного дефолта."""
    if not direction:
        return ""
    return ((direction.get("role_overrides") or {}).get(work_type) or "").strip()

# Что может делать каждый тип роли: prefix роли → допустимые bucket-категории.
# Используется чтобы не отдать «Тестирование»/«Анализ» разработчику, даже если
# направление сконфигурировано неправильно (role_overrides указывает
# на несовместимую роль).
_ROLE_WORK_CATEGORIES: dict[str, frozenset[str]] = {
    "analyst":   frozenset({"Анализ", "Тестирование"}),
    "tester":    frozenset({"Тестирование"}),
    "developer": frozenset({"Разработка", "Код-ревью", "Релиз"}),
    "designer":  frozenset({"Дизайн", "Дизайн-ревью"}),
}


def _role_allowed_buckets(role: str | None) -> frozenset[str] | None:
    """Множество bucket-категорий, доступных роли. None = без ограничений."""
    if not role:
        return None
    for prefix, cats in _ROLE_WORK_CATEGORIES.items():
        if role.startswith(prefix):
            return cats
    return None


def _safe_content_role(role: str, bucket: str) -> str:
    """Если role не подходит для bucket (например, role_overrides направления по
    ошибке указывает на роль разработчика) — откатываемся на дефолтную
    «analyst», которая совместима и с «Анализ», и с «Тестирование».
    """
    allowed = _role_allowed_buckets(role)
    if allowed is not None and bucket not in allowed:
        return "analyst"
    return role


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

    «Релиз» — не работа, а сигнал готовности (см. _REVIEW_BUCKETS), часы всегда 0:
    веха не должна попадать в плановые часы / стоимость / суммы по сводным полосам.
    """
    if bucket == "Релиз":
        return 0.0
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


# Поле направления work_types → роли, обязательные для этого пайплайна.
# Конфигурируется через уже существующий work_types направления, без новых полей конфига.
_WORK_TYPES_TO_REQUIRED_ROLES: dict[str, list[str]] = {
    "design": ["responsible", "designer"],
    "development": ["responsible", "developer", "tester"],
}

# Роль → атрибут SprintConfig с id персонального поля Jira.
_ROLE_TO_CONFIG_FIELD: dict[str, str] = {
    "responsible": "responsible_field",
    "developer": "developer_field",
    "designer": "designer_field",
    "tester": "tester_field",
}


def compute_missing_assignees(issues: list[dict], cfg: SprintConfig, base_url: str) -> list[dict]:
    """Задачи направлений design/development без хотя бы одного исполнителя пайплайна.

    Правило берётся из work_types направления задачи (см. _find_direction):
    design → нужны аналитик и дизайнер; development → нужны аналитик, разработчик
    и тестировщик. Роли, для которых в конфиге не настроено поле Jira, не проверяются.
    Закрытые задачи (terminal_statuses) и задачи без определённого направления
    пропускаются.
    """
    terminal = set(cfg.terminal_statuses)
    result: list[dict] = []

    for issue in issues:
        f = issue.get("fields", {})
        status_name = (f.get("status") or {}).get("name", "")
        if status_name in terminal:
            continue

        direction = _find_direction(f.get("labels") or [], cfg)
        if not direction:
            continue

        needed: list[str] = []
        for wt in direction.get("work_types", []):
            for role in _WORK_TYPES_TO_REQUIRED_ROLES.get(wt, []):
                if role not in needed:
                    needed.append(role)
        needed = [r for r in needed if getattr(cfg, _ROLE_TO_CONFIG_FIELD[r])]
        if not needed:
            continue

        current: dict[str, str | None] = {}
        missing: list[str] = []
        for role in needed:
            field_id = getattr(cfg, _ROLE_TO_CONFIG_FIELD[role])
            acc_id = _field_account_id(f, field_id)
            current[role] = acc_id
            if not acc_id:
                missing.append(role)
        if not missing:
            continue

        result.append({
            "key": issue["key"],
            "url": f"{base_url}/browse/{issue['key']}",
            "summary": f.get("summary", ""),
            "direction": direction.get("name"),
            "missing": missing,
            "responsible_id": current.get("responsible"),
            "developer_id": current.get("developer"),
            "designer_id": current.get("designer"),
            "tester_id": current.get("tester"),
        })

    return result


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


def _resolve_release_owner(
    dev_id: str | None, dev_name: str | None, cfg: SprintConfig,
    dev_lead: tuple[str, dict] | None,
) -> tuple[str, str, str] | None:
    """Владелец будущей/пост-аллокационной вехи «Релиз»: приоритет — человек из поля
    «Разработчик», иначе лид разработки. Роль кандидата всегда "developer_lead" — так
    заведены дефолтные часы (role_status_default_hours), вне зависимости от реальной
    роли человека из поля «Разработчик» (developer/_frontend/_backend).

    Используется для шагов, которые ещё не наступили (генерируются заранее) — для
    шага, уже стоящего в текущем статусе задачи, роль берётся иначе (см.
    _process_issue_for_role: там в Ганте фигурирует фактическая роль разработчика).

    Возвращает (owner_id, role, file_name) или None.
    """
    if dev_id:
        name = cfg.team[dev_id]["file_name"] if dev_id in cfg.team else (dev_name or dev_id)
        return dev_id, "developer_lead", name
    if dev_lead:
        lead_id, lead_info = dev_lead
        return lead_id, "developer_lead", lead_info["file_name"]
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


def _field_account_id(f: dict, field_id: str | None) -> str | None:
    """accountId из персонального поля Jira (user-picker), либо None."""
    if not field_id:
        return None
    val = f.get(field_id) or {}
    if not isinstance(val, dict):
        return None
    return val.get("accountId") or None


def _person_from_field(
    f: dict, field_id: str | None, cfg: SprintConfig, default_role: str,
) -> tuple[str | None, str, dict[str, dict]]:
    """Владелец шага из персонального поля Jira («Дизайнер»/«Тестировщик»).

    Если поле заполнено — берём указанного человека безусловно (как developer_field):
    - человек в команде конфига → его фактическая роль и запись из team;
    - иначе → синтетическая запись с displayName из Jira и default_role.

    Возвращает (owner_id, role, role_team) или (None, default_role, {}) если поле пусто.
    """
    if not field_id:
        return None, default_role, {}
    val = f.get(field_id) or {}
    if not isinstance(val, dict):
        return None, default_role, {}
    acc_id = val.get("accountId")
    if not acc_id:
        return None, default_role, {}
    if acc_id in cfg.team:
        role = cfg.team[acc_id].get("role") or default_role
        return acc_id, role, {acc_id: cfg.team[acc_id]}
    display = val.get("displayName") or acc_id
    return acc_id, default_role, {acc_id: {"file_name": display, "role": default_role, "salary": 0}}


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
        "hours_designer": f.get(cfg.role_hours_fields.get("designer", "")) or None,
        "hours_original": orig_hours,
        "direction": direction,
        "labels": labels,
        "responsible_id": responsible_id,
        "assignee_id": assignee_id,
        "reporter_id": reporter_id,
        "developer_name": _extract_developer_name(f, cfg),
        "developer_id": _field_account_id(f, cfg.developer_field),
        "designer_id": _field_account_id(f, cfg.designer_field),
        "tester_id": _field_account_id(f, cfg.tester_field),
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

    # Персональные поля Jira имеют приоритет для своих фаз:
    # «Дизайнер» → шаг дизайна, «Тестировщик» → шаг тестирования.
    field_override = False
    if bucket == "Дизайн" and cfg.designer_field:
        fid, _frole, fteam = _person_from_field(f, cfg.designer_field, cfg, role)
        if fid:
            owner_id, role_team, field_override = fid, fteam, True
    elif bucket == "Тестирование" and cfg.tester_field:
        fid, _frole, fteam = _person_from_field(f, cfg.tester_field, cfg, role)
        if fid:
            owner_id, role_team, field_override = fid, fteam, True
    elif bucket == "Релиз":
        # Веха «Релиз»: приоритет — человек из поля «Разработчик», иначе лид разработки.
        # Роль берём фактическую (frole), а не дефолтную «лид» — релизит себя сам
        # разработчик, и в Ганте он должен отображаться разработчиком, а не лидом.
        fid, frole, fteam = _person_from_field(f, cfg.developer_field, cfg, role)
        if fid:
            owner_id, role, role_team, field_override = fid, frole, fteam, True
        else:
            lead = _find_lead_owner(cfg, "developer_lead")
            if lead:
                lead_id, lead_info = lead
                owner_id, role_team, field_override = lead_id, {lead_id: lead_info}, True

    if owner_id is None:
        return

    key = issue["key"]
    cand_key = (key, role, bucket)
    if cand_key in by_key_role:
        return

    formal_only = False
    if not field_override and role == "analyst" and assignee_id not in role_team:
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
    f: dict, direction: dict, cfg: SprintConfig,
    team_by_role: dict[str, dict[str, dict]],
    assignee_id: str | None,
) -> tuple[str | None, dict[str, dict]]:
    """Определить владельца шага дизайна для задачи из направления.

    Порядок:
    1. Поле Jira «Дизайнер» (designer_field) — безусловный приоритет.
    2. Assignee, если он в команде с ролью designer.
    3. direction["designer_id"] — явно выбранный в настройках направления.
    4. Единственный/первый в команде с ролью designer.
    """
    role_team = team_by_role.get("designer") or _team_with_role(cfg, "designer")

    # 1. Поле «Дизайнер» из Jira — приоритет (как developer_field для разработки).
    fid, _frole, fteam = _person_from_field(f, cfg.designer_field, cfg, "designer")
    if fid:
        return fid, fteam

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
    dev_role = _role_override(direction, "development") or "developer"
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


def _historical_tester_id(issue: dict) -> str | None:
    """account_id того, кто был исполнителем, пока задача РЕАЛЬНО находилась в
    статусе тестирования (по названию статуса — содержит «тест»).

    Определяем по названию статуса, а не по бакету role_status_buckets: легаси-
    маппинг analyst→Тестирование помечает «тест-фазой» и нетестовые статусы
    (Код-ревью и т.п.), что дало бы ложного историчного тестировщика.
    Возвращает исполнителя последней тест-фазы или None, если её не было.
    """
    if not issue.get("changelog", {}).get("histories"):
        return None
    from datetime import datetime, timedelta
    from app.sprint.epic_history import (
        _assignee_at, _assignee_transitions, _parse_jira_dt, _status_transitions,
    )

    f = issue["fields"]
    created = _parse_jira_dt(f.get("created")) or datetime.now()
    initial_status, transitions = _status_transitions(issue)
    initial_assignee, assignee_changes = _assignee_transitions(issue)
    current_assignee = (
        (f.get("assignee") or {}).get("accountId"),
        (f.get("assignee") or {}).get("displayName"),
    )

    segments: list[tuple[str, datetime]] = []
    cur_status = initial_status or (f.get("status") or {}).get("name", "")
    cur_start = created
    for dt, to in transitions:
        if dt > cur_start:
            segments.append((cur_status, cur_start))
        cur_status, cur_start = to, dt
    segments.append((cur_status, cur_start))

    grace = timedelta(seconds=300)
    last_tester: str | None = None
    for status, start_dt in segments:
        if "тест" not in (status or "").lower():
            continue
        oid, _ = _assignee_at(
            start_dt + grace, initial_assignee, assignee_changes, current_assignee,
        )
        if oid:
            last_tester = oid
    return last_tester


def _config_tester(
    direction: dict | None, tester_team: dict[str, dict],
) -> str | None:
    """Настроенный тестировщик направления, если роль тестировщика задана явно.

    Возвращает tester_id из конфига (или первого в команде роли) только когда
    role_overrides["testing"] непустой; иначе None (дефолтный analyst-режим не трогаем).
    """
    raw = _role_override(direction, "testing")
    if not raw or not tester_team:
        return None
    tester_id = (direction.get("tester_id") or "").strip()
    if tester_id and tester_id in tester_team:
        return tester_id
    return next(iter(tester_team))


def _resolve_tester_for_direction(
    issue: dict, direction: dict | None, cfg: SprintConfig,
    team_by_role: dict[str, dict[str, dict]],
    assignee_id: str | None, responsible_id: str | None, reporter_id: str | None,
) -> tuple[str | None, str, dict[str, dict]]:
    """Определить владельца шага тестирования для задачи направления.

    Порядок (согласовано с пользователем):
    1. Поле Jira «Тестировщик» (tester_field) — безусловный приоритет.
    2. Историчный тестировщик из changelog — кто реально тестил задачу в прошлом.
    3. Если роль тестировщика задана явно (role_overrides["testing"] != пусто) —
       настроенный тестировщик этой роли (tester_id, иначе единственный/первый в команде).
       Так будущие (ещё не тестированные) задачи получают тестировщика из конфига.
    4. Дефолт (role_overrides["testing"] пуст → analyst) — assignee→responsible→reporter,
       т.е. аналитик тестит свою задачу (старое поведение).

    Возвращает (owner_id, role, role_team).
    """
    raw = _role_override(direction, "testing")
    role = _safe_content_role(raw or "analyst", "Тестирование")
    role_team = team_by_role.get(role) or _team_with_role(cfg, role)

    # 1. Поле «Тестировщик» из Jira — приоритет (как developer_field для разработки).
    fid, frole, fteam = _person_from_field(issue["fields"], cfg.tester_field, cfg, role)
    if fid:
        return fid, frole, fteam

    # 2. Историчный исполнитель тест-фазы.
    hist_id = _historical_tester_id(issue)
    if hist_id and hist_id in cfg.team:
        hist_role = cfg.team[hist_id].get("role") or role
        return hist_id, hist_role, {hist_id: cfg.team[hist_id]}

    # 2. Явно заданная роль тестировщика → настроенный тестировщик из конфига.
    cfg_tester = _config_tester(direction, role_team)
    if cfg_tester:
        return cfg_tester, role, role_team

    # 3. Дефолт — цепочка владельцев задачи.
    owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
    return owner_id, role, role_team


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
                f, direction, cfg, team_by_role, assignee_id,
            )
        elif wt == "testing":
            role = _safe_content_role(_role_override(direction, "testing") or "analyst", bucket)
            role_team = team_by_role.get(role) or _team_with_role(cfg, role)
            owner_id = _resolve_owner(role, assignee_id, responsible_id, reporter_id, role_team)
        elif wt == "analytics":
            role = _safe_content_role(_role_override(direction, "analytics") or "analyst", bucket)
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
            "hours_designer": None,
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
            direction_dev_role = (_role_override(direction, "development") or "developer") if direction else None
            for role, bucket in role_buckets:
                # Для бакета «Разработка»: если у направления задан role_overrides["development"],
                # пропускаем роли разработчика, не совпадающие с этой ролью направления.
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
        return bool(task.get("hours_designer") or task.get("hours_original"))
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
        "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование", "Релиз",
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
    """Породить задачи тестирования, код-ревью, дизайн-ревью и релиза из выполненных задач.

    Для каждой non-partial задачи разработчика (bucket=Разработка):
      - Если направление включает «testing» → добавить задачу тестирования аналитику.
      - Всегда → добавить задачу код-ревью лиду разработки.
      - Если направление включает «release» → добавить веху релиза (см. _add_release).

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
        _dr = _role_override(_d, "development")
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

    # Веха «Релиз»: ключ задачи уже мог получить релиз через настоящий статус
    # (bucket="Релиз" в allocated) — дедуп тут по key, а не по (key, role, bucket),
    # так как итоговая роль владельца динамическая (поле «Разработчик» → лид разработки).
    released_keys: set[str] = {
        t["key"] for t in allocated
        if not t.get("is_pseudo") and t.get("bucket") == "Релиз"
    }

    def _release_owner(task: dict) -> tuple[str, str, str] | None:
        dev_id = (task.get("developer_id") or "").strip() or None
        return _resolve_release_owner(dev_id, task.get("developer_name"), cfg, dev_lead)

    def _add_release(task: dict, work_types: list[str]) -> None:
        if "release" not in work_types:
            return
        key = task["key"]
        if key in released_keys:
            return
        owner = _release_owner(task)
        if owner is None:
            return
        owner_id, owner_role, owner_name = owner
        # Часы релиза всегда 0 — см. estimate_hours_for_role: это не работа, а
        # сигнал готовности, не должен попадать в плановые часы / стоимость.
        derived.append(_make_derived(task, owner_role, "Релиз", owner_id, owner_name, 0.0))
        released_keys.add(key)

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
                    tester_role = _safe_content_role(
                        _role_override(direction, "testing") or "analyst",
                        "Тестирование",
                    )
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
                            # Явно заданная роль тестировщика → настроенный из конфига
                            if owner_id is None:
                                owner_id = _config_tester(direction, tester_team)
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

                elif wt == "release":
                    _add_release(task, work_types)

        # ---- Код-ревью завершено → тестирование (+ релиз) ----
        elif bucket == "Код-ревью":
            if direction:
                cr_idx = next((i for i, wt in enumerate(work_types) if wt == "code_review"), -1)
                has_testing = cr_idx >= 0 and any(wt == "testing" for wt in work_types[cr_idx + 1:])
            else:
                has_testing = True

            if has_testing:
                tester_role = _safe_content_role(
                    _role_override(direction, "testing") or "analyst",
                    "Тестирование",
                )
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
                    # Явно заданная роль тестировщика → настроенный из конфига
                    if owner_id is None:
                        owner_id = _config_tester(direction, tester_team)
                    if owner_id:
                        d = _make_derived(
                            task, tester_role, "Тестирование",
                            owner_id, tester_team[owner_id]["file_name"],
                            _tester_hours(task, tester_role, cfg),
                        )
                        derived.append(d)
                        allocated_keys.add(test_cand_key)

            _add_release(task, work_types)

        # ---- Тестирование завершено → релиз ----
        elif bucket == "Тестирование":
            _add_release(task, work_types)

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
