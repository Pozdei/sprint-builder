"""Прогноз реализации эпика."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_config
from app.db import models
from app.db.session import get_db
from app.jira.client import JiraError, client
from app.schemas.gantt import GanttItem
from app.sprint.config import from_dict
from app.sprint.epic_forecast import build_epic_forecast
from app.sprint.logic import find_story_points_field

router = APIRouter(prefix="/epic", tags=["epic"])


class EpicStats(BaseModel):
    total_issues: int
    done_issues: int
    remaining_work_items: int
    total_planned_hours: float
    default_hours_count: int


class EpicForecastResponse(BaseModel):
    epic_key: str
    epic_summary: str
    gantt_items: list[GanttItem]
    completion_date: str | None
    stats: EpicStats
    warnings: list[str]


def _fetch_issue_children(issue_key: str) -> tuple[str, str, list[dict]]:
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

    if is_epic:
        # Эпик: ищем дочерние задачи через Epic Link и parent
        for jql in [f'"Epic Link" = {issue_key}', f"parent = {issue_key}"]:
            try:
                data = client.get(
                    "/rest/api/3/search/jql",
                    params={"jql": jql, "maxResults": 200, "fields": base_fields},
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
                params={
                    "jql": f"parent = {issue_key}",
                    "maxResults": 200,
                    "fields": base_fields,
                },
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
    config: models.Config = Depends(current_config),
    db: Session = Depends(get_db),
):
    """Прогноз реализации эпика: Гант + предиктная дата завершения."""
    from app.db import repository

    cfg_model = config
    cfg_dict = repository.model_to_sprint_config_dict(cfg_model)
    cfg = from_dict(cfg_dict)
    cfg_snapshot = {"id": cfg_model.id, **cfg_dict}

    # Получаем задачи (эпик → дочерние; обычная задача → сама или подзадачи)
    try:
        issue_summary, issue_type, issues = _fetch_issue_children(key)
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

    result = build_epic_forecast(
        issues, cfg, sp_field, base_url, start_date, hours_per_day,
    )

    return EpicForecastResponse(
        epic_key=key,
        epic_summary=issue_summary,
        gantt_items=result["gantt_items"],
        completion_date=result["completion_date"],
        stats=EpicStats(**result["stats"]),
        warnings=result["warnings"],
    )
