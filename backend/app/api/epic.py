"""Прогноз реализации эпика."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_config
from app.db import models, repository
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.gantt import GanttItem, TaskDependency
from app.sprint.config import from_dict
from app.sprint.epic_forecast import build_epic_forecast
from app.sprint.logic import find_story_points_field

router = APIRouter(prefix="/epic", tags=["epic"])


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


class CostBreakdownItem(BaseModel):
    name: str
    hours: float
    salary: int
    cost: float


class EpicForecastResponse(BaseModel):
    epic_key: str
    epic_summary: str
    gantt_items: list[GanttItem]
    completion_date: str | None
    stats: EpicStats
    cost_breakdown: list[CostBreakdownItem] = []
    warnings: list[str]


def _fetch_issue_children(
    issue_key: str,
    expand_changelog: bool = False,
) -> tuple[str, str, list[dict]]:
    """Получить задачи для прогноза из Jira.

    Для эпика → дочерние задачи (Epic Link + parent).
    Для обычной задачи → сама задача (если нет дочерних) или её подзадачи.

    Возвращает (summary, issue_type_name, список задач).
    """
    base_fields = (
        "summary,status,issuetype,assignee,reporter,labels,"
        "timeoriginalestimate,customfield_10020"
    )

    # Основная задача
    issue_data = client.get(
        f"/rest/api/3/issue/{issue_key}",
        params={"fields": "summary,issuetype"},
    )
    issue_fields = issue_data.get("fields", {})
    issue_type = (issue_fields.get("issuetype") or {}).get("name", "")
    summary = issue_fields.get("summary", "")

    is_epic = issue_type.lower() in ("эпик", "epic")
    issues: list[dict] = []

    extra_params: dict = {"maxResults": 200, "fields": base_fields}
    if expand_changelog:
        extra_params["expand"] = "changelog"

    if is_epic:
        # Эпик: ищем дочерние задачи через Epic Link и parent
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


def _enrich_with_config_fields(issues: list[dict], cfg_snapshot: dict) -> list[dict]:
    """Дозапросить кастомные поля (часы, responsible, developer) для всех задач."""
    extra_fields = [
        cfg_snapshot.get("responsible_field", ""),
        cfg_snapshot.get("developer_field", ""),
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
    key: str = Query(..., description="Ключ эпика, например SHN-1947"),
    start_date: date = Query(..., description="Дата начала расчёта, напр. 2025-01-20"),
    hours_per_day: float = Query(8.0, ge=1, le=24),
    use_history: bool = Query(False, description="Учитывать историю статусов при определении этапов"),
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    """Прогноз реализации эпика: Гант + предиктная дата завершения."""
    cfg_model = config
    cfg_dict = repository.model_to_sprint_config_dict(cfg_model)
    cfg = from_dict(cfg_dict)
    cfg_snapshot = {"id": cfg_model.id, **cfg_dict}

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

    # Получаем задачи (эпик → дочерние; обычная задача → сама или подзадачи)
    try:
        issue_summary, _issue_type, issues = _fetch_issue_children(
            key, expand_changelog=use_history,
        )
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not issues:
        raise HTTPException(status_code=404, detail=f"Задачи для {key} не найдены")

    # Дозапрашиваем кастомные поля (часы, разработчик)
    issues = _enrich_with_config_fields(issues, cfg_snapshot)

    # Подставляем правильный sprint_field в задачи (он уже в fields)
    try:
        sp_field = find_story_points_field(client)
    except JiraError:
        sp_field = None

    base_url = client.base_url

    # Отпуска из конфига
    vacations = repository.vacations_to_dicts(cfg_model.vacations)

    # FS-зависимости эпика
    epic_deps = repository.list_epic_dependencies(db, cfg_model.id, key)
    dependencies = [{"from_key": d.from_key, "to_key": d.to_key} for d in epic_deps]

    result = build_epic_forecast(
        issues, cfg, sp_field, base_url, start_date, hours_per_day,
        dependencies=dependencies,
        vacations=vacations,
        use_history=use_history,
    )

    # Автосохранение снапшота (один в день, upsert)
    today = date.today().isoformat()
    stats = result["stats"]
    repository.upsert_epic_snapshot(
        db=db,
        config_id=cfg_model.id,
        epic_key=key,
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
        epic_key=key,
        epic_summary=issue_summary,
        gantt_items=result["gantt_items"],
        completion_date=result["completion_date"],
        stats=EpicStats(**result["stats"]),
        cost_breakdown=[CostBreakdownItem(**item) for item in result.get("cost_breakdown", [])],
        warnings=result["warnings"],
    )
