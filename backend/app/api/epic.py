"""Прогноз реализации эпика."""

import urllib.parse
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_config
from app.db import models, repository, sprints_repository
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.gantt import GanttItem, TaskDependency
from app.sprint.config import from_dict
from app.sprint.epic_forecast import build_epic_forecast
from app.sprint.excel import build_epic_forecast_xlsx
from app.sprint.logic import find_story_points_field

router = APIRouter(prefix="/epic", tags=["epic"])

# Базовый набор полей Jira для задач прогноза.
_BASE_FORECAST_FIELDS = (
    "summary,status,issuetype,assignee,reporter,labels,created,parent,"
    "timeoriginalestimate,customfield_10020"
)


class EpicDependencyRequest(BaseModel):
    from_key: str
    to_key: str


class EpicSnapshotOut(BaseModel):
    id: int
    epic_key: str
    captured_date: str
    start_date: str
    hours_per_day: float
    completion_date: str | None
    total_issues: int
    done_issues: int
    remaining_work_items: int
    total_planned_hours: float
    is_pinned: bool = False


def _to_dep_list(deps) -> list[TaskDependency]:
    return [TaskDependency(from_key=d.from_key, to_key=d.to_key) for d in deps]


def _snapshot_to_out(s: models.EpicForecastSnapshot) -> "EpicSnapshotOut":
    return EpicSnapshotOut(
        id=s.id, epic_key=s.epic_key, captured_date=s.captured_date,
        start_date=s.start_date, hours_per_day=s.hours_per_day,
        completion_date=s.completion_date, total_issues=s.total_issues,
        done_issues=s.done_issues, remaining_work_items=s.remaining_work_items,
        total_planned_hours=s.total_planned_hours,
        is_pinned=s.is_pinned,
    )


@router.get("/dependencies", response_model=list[TaskDependency])
def get_epic_dependencies(
    epic_key: str = Query(...),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return _to_dep_list(repository.list_epic_dependencies(db, config.id, epic_key))


@router.post("/dependencies", response_model=list[TaskDependency], status_code=201)
def add_epic_dependency(
    body: EpicDependencyRequest,
    epic_key: str = Query(...),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    if body.from_key == body.to_key:
        raise HTTPException(status_code=422, detail="Задача не может зависеть от самой себя")
    deps = repository.add_epic_dependency(db, config.id, epic_key, body.from_key, body.to_key)
    db.commit()
    return _to_dep_list(deps)


@router.delete("/dependencies", status_code=204)
def remove_epic_dependency(
    body: EpicDependencyRequest,
    epic_key: str = Query(...),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    repository.remove_epic_dependency(db, config.id, epic_key, body.from_key, body.to_key)
    db.commit()


@router.get("/snapshots", response_model=list[EpicSnapshotOut])
def get_epic_snapshots(
    epic_key: str = Query(...),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    return [_snapshot_to_out(s) for s in repository.list_epic_snapshots(db, config.id, epic_key)]


@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_epic_snapshot(
    snapshot_id: int,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    if not repository.delete_epic_snapshot(db, snapshot_id, config.id):
        raise HTTPException(status_code=404, detail="Снапшот не найден")
    db.commit()


@router.patch("/snapshots/{snapshot_id}/pin", response_model=EpicSnapshotOut)
def pin_epic_snapshot(
    snapshot_id: int,
    pinned: bool = True,
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    snap = repository.pin_epic_snapshot(db, snapshot_id, config.id, pinned)
    if not snap:
        raise HTTPException(status_code=404, detail="Снапшот не найден")
    db.commit()
    return _snapshot_to_out(snap)


class EpicStats(BaseModel):
    total_issues: int
    done_issues: int
    remaining_work_items: int
    total_planned_hours: float
    default_hours_count: int
    total_cost: float = 0.0
    # Историчный режим: разбивка потрачено (прошлое) / осталось (будущее)
    spent_hours: float = 0.0
    spent_cost: float = 0.0
    remaining_hours: float = 0.0
    remaining_cost: float = 0.0


class CostBreakdownItem(BaseModel):
    name: str
    hours: float
    salary: int
    cost: float


class CurrentSprint(BaseModel):
    sprint_num: int | None = None
    start_date: str   # YYYY-MM-DD
    end_date: str     # YYYY-MM-DD


class EpicForecastResponse(BaseModel):
    epic_key: str
    epic_summary: str
    gantt_items: list[GanttItem]
    completion_date: str | None
    stats: EpicStats
    cost_breakdown: list[CostBreakdownItem] = []
    warnings: list[str]
    gantt_start: str | None = None   # начало шкалы Ганта (для истор. режима — origin)
    today_hours: float | None = None  # рабочие часы от начала шкалы до «сегодня»
    current_sprint: CurrentSprint | None = None  # активный спринт (для границ на Ганте)


def _fetch_issue_children(
    issue_key: str,
    expand_changelog: bool = False,
) -> tuple[str, str, list[dict]]:
    """Получить задачи для прогноза из Jira.

    Для эпика → дочерние задачи (Epic Link + parent).
    Для обычной задачи → сама задача (если нет дочерних) или её подзадачи.

    Возвращает (summary, issue_type_name, список задач).
    """
    base_fields = _BASE_FORECAST_FIELDS

    # Основная задача (+ issuelinks, чтобы достать детей через связь «Parent»)
    issue_data = client.get(
        f"/rest/api/3/issue/{issue_key}",
        params={"fields": "summary,issuetype,issuelinks"},
    )
    issue_fields = issue_data.get("fields", {})
    issue_type = (issue_fields.get("issuetype") or {}).get("name", "")
    summary = issue_fields.get("summary", "")

    # Эпик и История — агрегаты: разворачиваем в дочерние задачи.
    is_aggregate = issue_type.lower() in (
        "эпик", "epic", "история", "story", "user story", "пользовательская история",
    )
    issues: list[dict] = []

    extra_params: dict = {"maxResults": 200, "fields": base_fields}
    if expand_changelog:
        extra_params["expand"] = "changelog"

    if is_aggregate:
        # Агрегат: ищем дочерние задачи через Epic Link и поле parent
        for jql in [f'"Epic Link" = {issue_key}', f"parent = {issue_key}"]:
            try:
                data = client.get(
                    "/rest/api/3/search/jql",
                    params={"jql": jql, **extra_params},
                )
                for iss in data.get("issues", []):
                    if not any(i["key"] == iss["key"] for i in issues):
                        issues.append(iss)
            except JiraError:
                pass

        # Дети через issue-link «Parent» (родитель «Is parent of» → outwardIssue).
        # Так подтягиваются задачи внутри Истории, привязанные связью, а не полем.
        link_child_keys: list[str] = []
        for link in issue_fields.get("issuelinks") or []:
            t = link.get("type") or {}
            if (t.get("name") or "").lower() not in _PARENT_LINK_NAMES:
                continue
            outw = link.get("outwardIssue")
            if isinstance(outw, dict) and outw.get("key"):
                link_child_keys.append(outw["key"])
        missing = [k for k in link_child_keys if not any(i["key"] == k for i in issues)]
        if missing:
            try:
                for iss in _fetch_issues_by_keys(missing, expand_changelog=expand_changelog):
                    if not any(i["key"] == iss["key"] for i in issues):
                        issues.append(iss)
            except JiraError:
                pass
    else:
        # Обычная задача: сначала ищем подзадачи
        try:
            data = client.get(
                "/rest/api/3/search/jql",
                params={"jql": f"parent = {issue_key}", **extra_params},
            )
            issues = data.get("issues", [])
        except JiraError:
            pass

        # Нет подзадач → сама задача является единицей работы
        if not issues:
            full = client.get(
                f"/rest/api/3/issue/{issue_key}",
                params={"fields": base_fields},
            )
            issues = [full]

    return summary, issue_type, issues


def _sprint_task_keys(sprint: models.Sprint) -> list[str]:
    """Уникальные ключи реальных (не псевдо) задач утверждённого спринта."""
    keys: list[str] = []
    seen: set[str] = set()
    for st in sprint.tasks:
        td = st.task_data or {}
        if td.get("is_pseudo"):
            continue
        key = td.get("key")
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _fetch_issues_by_keys(
    keys: list[str],
    expand_changelog: bool = False,
    fields: str = _BASE_FORECAST_FIELDS,
) -> list[dict]:
    """Загрузить задачи Jira по списку ключей (батчами по 50)."""
    issues: list[dict] = []
    extra_params: dict = {"maxResults": 100, "fields": fields}
    if expand_changelog:
        extra_params["expand"] = "changelog"

    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        jql = f"key in ({','.join(chunk)})"
        try:
            data = client.get("/rest/api/3/search/jql", params={"jql": jql, **extra_params})
        except JiraError:
            continue
        issues.extend(data.get("issues", []))
    return issues


_STORY_TYPES = ("история", "story", "user story", "пользовательская история")
_EPIC_TYPES = ("эпик", "epic")
# Тип связи Jira, выражающий иерархию «родитель-ребёнок» (Is parent of / Is child of)
_PARENT_LINK_NAMES = ("parent",)
_HIER_FIELDS = "issuetype,summary,parent,issuelinks"


def _field_parent_key(fields: dict) -> str | None:
    """Непосредственный родитель из поля `parent` (нативная иерархия Jira)."""
    p = fields.get("parent")
    return p["key"] if isinstance(p, dict) and p.get("key") else None


def _parent_candidates(fields: dict) -> list[str]:
    """Все родители задачи: поле `parent` + issue-link'и типа «Parent».

    В этой Jira эпик у задачи в поле `parent`, а история — отдельной связью
    «Parent» (задача «Is child of» истории, родитель приходит в `inwardIssue`).
    Поэтому для поиска предков нужно учитывать оба источника.
    """
    res: list[str] = []
    fp = _field_parent_key(fields)
    if fp:
        res.append(fp)
    for link in fields.get("issuelinks") or []:
        t = link.get("type") or {}
        if (t.get("name") or "").lower() not in _PARENT_LINK_NAMES:
            continue
        inw = link.get("inwardIssue")
        if isinstance(inw, dict) and inw.get("key"):
            res.append(inw["key"])
    out: list[str] = []
    seen: set[str] = set()
    for k in res:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _issuelink_keys(fields: dict) -> list[str]:
    """Соседи задачи по «боковым» issue-link'ам (Blocks, Relates, Duplicate, Clones…).

    Используется для «Консолидировано» — кластеризации по смыслу связанных задач.
    Иерархические связи (поле `parent` и issue-link «Parent») сюда НЕ включаем: они
    реконструируют дерево эпик/история, для которых есть отдельные полосы.
    """
    res: list[str] = []
    for link in fields.get("issuelinks") or []:
        t = link.get("type") or {}
        if (t.get("name") or "").lower() in _PARENT_LINK_NAMES:
            continue
        for side in ("inwardIssue", "outwardIssue"):
            o = link.get(side)
            if isinstance(o, dict) and o.get("key"):
                res.append(o["key"])
    return res


def _sprint_info_from_issues(issues: list[dict], cfg) -> dict | None:
    """Активный спринт из поля спринта задач прогноза (не зависит от борд конфига).

    Поле спринта Jira возвращает объекты со state/startDate/endDate. Берём активный
    спринт с наибольшим номером; если активных нет — любой с датами и макс. номером.
    """
    import re as _re
    field = cfg.sprint_field
    if not field:
        return None
    active: list[tuple] = []
    dated: list[tuple] = []
    for iss in issues:
        val = iss.get("fields", {}).get(field)
        if not isinstance(val, list):
            continue
        for sp in val:
            if not isinstance(sp, dict):
                continue
            start, end = sp.get("startDate"), sp.get("endDate")
            if not (start and end):
                continue
            m = _re.search(r"(\d+)", sp.get("name") or "")
            num = int(m.group(1)) if m else None
            rec = (num if num is not None else -1, start[:10], end[:10], num)
            dated.append(rec)
            if (sp.get("state") or "").lower() == "active":
                active.append(rec)
    pool = active or dated
    if not pool:
        return None
    best = max(pool, key=lambda r: r[0])
    return {"sprint_num": best[3], "start_date": best[1], "end_date": best[2]}


def _active_sprint_info(cfg) -> dict | None:
    """Активный спринт борды: {sprint_num, start_date, end_date} или None.

    Нужен для отрисовки границ спринтов на Ганте прогноза. Берём первую борду
    конфига с активным спринтом, у которого заданы даты начала и конца.
    """
    import re as _re
    for board_id in cfg.boards.values():
        try:
            data = client.get(
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={"state": "active"},
            )
        except JiraError:
            continue
        for sp in data.get("values", []):
            start = sp.get("startDate")
            end = sp.get("endDate")
            if not (start and end):
                continue
            m = _re.search(r"(\d+)", sp.get("name") or "")
            return {
                "sprint_num": int(m.group(1)) if m else None,
                "start_date": start[:10],
                "end_date": end[:10],
            }
    return None


def _annotate_hierarchy(gantt_items: list[dict], issues: list[dict]) -> None:
    """Проставить parent_/story_/epic_ ключи каждому бару (для сводных полос).

    - parent_* — «Консолидировано»: связные компоненты по issue-link'ам любого типа
      (Blocks, Relates, Parent-link, дубликаты…), т.е. кластеры связанных задач;
    - story_*  — первый предок с типом «История» (свод по User Story);
    - epic_*   — первый предок с типом «Эпик» (свод по эпикам).

    Предки/связи догружаем из Jira батчами. Псевдо/служебные бары не размечаем.
    """
    # info: key -> {"type", "summary", "field_parent", "parents": [str], "links": [str]}
    info: dict[str, dict] = {}

    def absorb(iss: dict) -> None:
        f = iss.get("fields", {})
        info[iss["key"]] = {
            "type": (f.get("issuetype") or {}).get("name", "").lower(),
            "summary": f.get("summary"),
            "field_parent": _field_parent_key(f),
            "parents": _parent_candidates(f),
            "links": _issuelink_keys(f),
        }

    # Стартовые ключи — реальные задачи прогноза
    start_keys: list[str] = []
    seen_start: set[str] = set()
    for item in gantt_items:
        k = item.get("key", "")
        if item.get("is_pseudo") or k.startswith("__") or k.startswith("pseudo") or k in seen_start:
            continue
        seen_start.add(k)
        start_keys.append(k)

    # Поднимаемся по дереву уровень за уровнем (issuelinks есть только при отдельном
    # запросе по ключу, поэтому дозапрашиваем каждый узел)
    fetched: set[str] = set()
    frontier = list(start_keys)
    for _ in range(8):
        need = [k for k in frontier if k not in fetched]
        if not need:
            break
        try:
            batch = _fetch_issues_by_keys(need, fields=_HIER_FIELDS)
        except JiraError:
            break
        next_frontier: list[str] = []
        for iss in batch:
            absorb(iss)
            fetched.add(iss["key"])
            for pk in info[iss["key"]]["parents"]:
                if pk not in fetched:
                    next_frontier.append(pk)
        frontier = next_frontier

    def ancestor_of_type(key: str, types: tuple[str, ...]) -> str | None:
        from collections import deque
        seen: set[str] = set()
        q: deque[str] = deque(info.get(key, {}).get("parents", []))
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            if info.get(cur, {}).get("type") in types:
                return cur
            q.extend(info.get(cur, {}).get("parents", []))
        return None

    # ----- Консолидировано: связные компоненты по issue-link'ам -----
    uf: dict[str, str] = {}

    def find(x: str) -> str:
        uf.setdefault(x, x)
        root = x
        while uf[root] != root:
            root = uf[root]
        while uf[x] != root:
            uf[x], x = root, uf[x]
        return root

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            uf[ra] = rb

    # Кластеризуем ТОЛЬКО задачи прогноза между собой (эпик/история не должны быть
    # хабом — иначе кластер вырождается в эпик). Связь учитываем, если оба конца —
    # задачи прогноза.
    work_set = set(start_keys)
    for k in start_keys:
        for nb in info.get(k, {}).get("links", []):
            if nb in work_set:
                union(k, nb)
        find(k)   # одиночная задача без связей — свой компонент

    from collections import defaultdict
    members: dict[str, list[str]] = defaultdict(list)
    for k in start_keys:
        members[find(k)].append(k)

    # Представитель кластера — задача с наибольшим числом связей внутри кластера
    # (хаб), при равенстве — наименьший ключ. По нему подписываем «колбасу».
    def representative(ms: list[str]) -> str:
        if len(ms) == 1:
            return ms[0]
        ms_set = set(ms)
        def degree(m: str) -> int:
            return sum(1 for nb in info.get(m, {}).get("links", []) if nb in ms_set)
        return sorted(ms, key=lambda m: (-degree(m), m))[0]

    rep_of_root: dict[str, str] = {root: representative(ms) for root, ms in members.items()}

    for item in gantt_items:
        key = item.get("key", "")
        if item.get("is_pseudo") or key.startswith("__") or key.startswith("pseudo"):
            continue
        # Консолидировано — только кластеры из >1 связанной задачи (одиночки не группируем)
        root = find(key) if key in uf else None
        cluster = members.get(root, []) if root is not None else []
        if len(cluster) > 1:
            rep = rep_of_root[root]
            item["parent_key"] = rep
            item["parent_summary"] = info.get(rep, {}).get("summary")
        else:
            item["parent_key"] = None
            item["parent_summary"] = None
        # Свод по User Story / Epic — по предку нужного типа
        story = ancestor_of_type(key, _STORY_TYPES)
        epic = ancestor_of_type(key, _EPIC_TYPES)
        item["story_key"] = story
        item["story_summary"] = info.get(story, {}).get("summary") if story else None
        item["epic_key"] = epic
        item["epic_summary"] = info.get(epic, {}).get("summary") if epic else None


def _fetch_full_changelog(issue_key: str) -> list[dict]:
    """Полная история изменений задачи (пагинация).

    `expand=changelog` в /search/jql может усекаться, поэтому в истор. режиме
    дотягиваем changelog отдельным эндпоинтом — для корректных самых ранних дат.
    """
    histories: list[dict] = []
    start_at = 0
    for _ in range(50):  # предохранитель от бесконечного цикла
        try:
            data = client.get(
                f"/rest/api/3/issue/{issue_key}/changelog",
                params={"startAt": start_at, "maxResults": 100},
            )
        except JiraError:
            break
        values = data.get("values", [])
        histories.extend(values)
        start_at += len(values)
        if data.get("isLast") or not values or start_at >= data.get("total", 0):
            break
    return histories


def _enrich_with_config_fields(issues: list[dict], cfg_snapshot: dict) -> list[dict]:
    """Дозапросить кастомные поля (часы, responsible, developer) для всех задач."""
    extra_fields = [
        cfg_snapshot.get("responsible_field", ""),
        cfg_snapshot.get("developer_field", ""),
        cfg_snapshot.get("designer_field", ""),
        cfg_snapshot.get("tester_field", ""),
        cfg_snapshot.get("sprint_field", ""),
        *cfg_snapshot.get("role_hours_fields", {}).values(),
    ]
    extra_fields = [f for f in extra_fields if f]
    if not extra_fields:
        return issues

    # Батчевый запрос
    keys = ",".join(i["key"] for i in issues)
    extra_fields_str = ",".join(extra_fields)
    try:
        data = client.get(
            "/rest/api/3/search/jql",
            params={
                "jql": f"key in ({keys})",
                "maxResults": 200,
                "fields": extra_fields_str,
            },
        )
        enriched_map = {i["key"]: i["fields"] for i in data.get("issues", [])}
        for issue in issues:
            extra = enriched_map.get(issue["key"], {})
            issue["fields"].update({k: v for k, v in extra.items() if k not in issue["fields"] or issue["fields"][k] is None})
    except JiraError:
        pass  # не критично — используем defaults

    return issues


@router.get("/forecast", response_model=EpicForecastResponse)
def epic_forecast(
    key: str | None = Query(None, description="Ключ эпика, например SHN-1947"),
    sprint_id: int | None = Query(None, description="ID утверждённого спринта — источник задач вместо эпика"),
    start_date: date = Query(..., description="Дата начала расчёта, напр. 2025-01-20"),
    hours_per_day: float = Query(8.0, ge=1, le=24),
    use_history: bool = Query(False, description="Учитывать историю статусов при определении этапов"),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    """Прогноз реализации: Гант + предиктная дата завершения.

    Источник задач — либо эпик/задача из Jira (`key`), либо утверждённый спринт
    (`sprint_id`): тогда берём состав задач из снапшота спринта и прогоняем
    тем же алгоритмом прогноза.
    """
    cfg_model = config
    cfg_dict = repository.model_to_sprint_config_dict(cfg_model)
    cfg = from_dict(cfg_dict)
    cfg_snapshot = {"id": cfg_model.id, **cfg_dict}

    # Источник задач: утверждённый спринт или эпик
    sprint: models.Sprint | None = None
    if sprint_id is not None:
        sprint = sprints_repository.get_sprint(db, sprint_id)
        if not sprint or sprint.config_id != cfg_model.id:
            raise HTTPException(status_code=404, detail=f"Спринт {sprint_id} не найден")
        if sprint.status != "approved":
            raise HTTPException(
                status_code=409,
                detail=f"Прогноз можно строить только по утверждённому спринту "
                       f"(спринт {sprint.sprint_num} — {sprint.status}).",
            )
    elif not key:
        raise HTTPException(
            status_code=422,
            detail="Укажите ключ эпика или выберите утверждённый спринт.",
        )

    # Оклады глобальны — берём максимальный salary по всем конфигам для каждого account_id.
    # Это нужно, чтобы прогноз видел зарплаты вне зависимости от активного конфига.
    team_ids = list(cfg.team.keys())
    if team_ids:
        all_members = db.query(models.TeamMember).filter(
            models.TeamMember.jira_account_id.in_(team_ids)
        ).all()
        global_salary: dict[str, int] = {}
        for tm in all_members:
            if tm.salary and tm.salary > 0:
                if tm.jira_account_id not in global_salary or tm.salary > global_salary[tm.jira_account_id]:
                    global_salary[tm.jira_account_id] = tm.salary
        for acc_id, info in cfg.team.items():
            if acc_id in global_salary:
                info["salary"] = global_salary[acc_id]

    # Получаем задачи: из утверждённого спринта или из эпика Jira
    if sprint is not None:
        sprint_keys = _sprint_task_keys(sprint)
        if not sprint_keys:
            raise HTTPException(
                status_code=404,
                detail=f"В спринте {sprint.sprint_num} нет задач для прогноза.",
            )
        try:
            issues = _fetch_issues_by_keys(sprint_keys, expand_changelog=use_history)
        except JiraError as e:
            raise HTTPException(status_code=502, detail=str(e))
        effective_key = f"sprint-{sprint.sprint_num}"
        issue_summary = f"Утверждённый спринт {sprint.sprint_num}"
    else:
        try:
            issue_summary, _issue_type, issues = _fetch_issue_children(
                key, expand_changelog=use_history,
            )
        except JiraError as e:
            raise HTTPException(status_code=502, detail=str(e))
        effective_key = key

    if not issues:
        raise HTTPException(status_code=404, detail=f"Задачи для {effective_key} не найдены")

    # Дозапрашиваем кастомные поля (часы, разработчик)
    issues = _enrich_with_config_fields(issues, cfg_snapshot)

    # В истор. режиме дотягиваем полную историю изменений по каждой задаче
    if use_history:
        for issue in issues:
            full = _fetch_full_changelog(issue["key"])
            if full:
                issue.setdefault("changelog", {})["histories"] = full

    # Подставляем правильный sprint_field в задачи (он уже в fields)
    try:
        sp_field = find_story_points_field(client)
    except JiraError:
        sp_field = None

    base_url = client.base_url

    # Отпуска из конфига
    vacations = repository.vacations_to_dicts(cfg_model.vacations)

    # FS-зависимости. Эпик: из таблицы под ключом. Спринт: захваченные в снапшоте +
    # добавленные пользователем в прогнозе (хранятся в той же таблице под "sprint-N").
    if sprint is not None:
        dependencies = []
        seen_deps: set[tuple] = set()
        captured = [
            {"from_key": d.get("from_key"), "to_key": d.get("to_key")}
            for d in (sprint.task_dependencies or [])
            if isinstance(d, dict) and d.get("from_key") and d.get("to_key")
        ]
        user_deps = repository.list_epic_dependencies(db, cfg_model.id, effective_key)
        for d in captured + [{"from_key": x.from_key, "to_key": x.to_key} for x in user_deps]:
            pair = (d["from_key"], d["to_key"])
            if pair not in seen_deps:
                seen_deps.add(pair)
                dependencies.append(d)
    else:
        epic_deps = repository.list_epic_dependencies(db, cfg_model.id, key)
        dependencies = [{"from_key": d.from_key, "to_key": d.to_key} for d in epic_deps]

    result = build_epic_forecast(
        issues, cfg, sp_field, base_url, start_date, hours_per_day,
        dependencies=dependencies,
        vacations=vacations,
        use_history=use_history,
    )

    # Иерархия стори/эпик для сводных полос — поднимаемся по дереву родителей
    _annotate_hierarchy(result["gantt_items"], issues)

    # Активный спринт — для отрисовки границ спринтов на Ганте.
    # Сначала из поля спринта задач (не зависит от борд), затем — из активного спринта борды.
    current_sprint = _sprint_info_from_issues(issues, cfg) or _active_sprint_info(cfg)

    # Автосохранение снапшота (один в день, upsert)
    today = date.today().isoformat()
    stats = result["stats"]
    repository.upsert_epic_snapshot(
        db=db,
        config_id=cfg_model.id,
        epic_key=effective_key,
        captured_date=today,
        start_date=start_date.isoformat(),
        hours_per_day=hours_per_day,
        completion_date=result["completion_date"],
        total_issues=stats["total_issues"],
        done_issues=stats["done_issues"],
        remaining_work_items=stats["remaining_work_items"],
        total_planned_hours=stats["total_planned_hours"],
    )
    db.commit()

    return EpicForecastResponse(
        epic_key=effective_key,
        epic_summary=issue_summary,
        gantt_items=result["gantt_items"],
        completion_date=result["completion_date"],
        stats=EpicStats(**result["stats"]),
        cost_breakdown=[CostBreakdownItem(**item) for item in result.get("cost_breakdown", [])],
        warnings=result["warnings"],
        gantt_start=result.get("gantt_start"),
        today_hours=result.get("today_hours"),
        current_sprint=CurrentSprint(**current_sprint) if current_sprint else None,
    )


class EpicForecastExportPayload(BaseModel):
    epic_key: str
    gantt_items: list[dict]


@router.post("/forecast/export")
def export_epic_forecast_xlsx(body: EpicForecastExportPayload):
    xlsx = build_epic_forecast_xlsx(body.gantt_items, body.epic_key)
    safe_name = urllib.parse.quote(f"forecast_{body.epic_key}.xlsx")
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"},
    )
