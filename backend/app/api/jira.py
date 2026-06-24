"""Jira: проверка подключения, поиск пользователей, обновление полей задач."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import current_config, get_jira_client, require_lead
from app.db import models
from app.jira.client import JiraError, client
from app.schemas.jira import (
    IssueFieldsUpdate, JiraUserOut,
    StandupSubmitRequest, StandupSubmitResult,
)

router = APIRouter(prefix="/jira", tags=["jira"])


@router.get("/check", dependencies=[Depends(get_jira_client)])
def jira_check():
    try:
        me = client.get("/rest/api/3/myself")
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"display_name": me.get("displayName"), "email": me.get("emailAddress")}

# Поля часов: (атрибут тела запроса, ключ в role_hours_fields, человекочитаемое имя)
_HOURS_ROLE_FIELDS = [
    ("hours_analyst",   "analyst",  "Часы аналитика"),
    ("hours_tester",    "tester",   "Часы тестера"),
    ("hours_developer", "developer","Часы разработчика"),
    ("hours_designer",  "designer", "Часы дизайнера"),
]


@router.patch("/issues/{key}/fields", status_code=204, dependencies=[Depends(get_jira_client)])
def update_issue_fields(
    key: str,
    body: IssueFieldsUpdate,
    config: models.Config = Depends(current_config),
):
    """Обновить поля задачи в Jira: часы ролей и/или разработчик."""
    from app.db import repository
    from app.sprint.config import from_dict
    cfg = from_dict(repository.model_to_sprint_config_dict(config))

    fields: dict = {}

    for attr, role_key, label in _HOURS_ROLE_FIELDS:
        value = getattr(body, attr)
        if value is None:
            continue
        fid = cfg.role_hours_fields.get(role_key)
        if not fid:
            raise HTTPException(status_code=400, detail=f"Поле '{label}' не настроено в конфиге")
        fields[fid] = value

    if body.developer_account_id is not None:
        if not cfg.developer_field:
            raise HTTPException(status_code=400, detail="Поле 'Разработчик' не настроено в конфиге")
        fields[cfg.developer_field] = {"accountId": body.developer_account_id}

    if body.designer_account_id is not None:
        if not cfg.designer_field:
            raise HTTPException(status_code=400, detail="Поле 'Дизайнер' не настроено в конфиге")
        fields[cfg.designer_field] = {"accountId": body.designer_account_id}

    if body.tester_account_id is not None:
        if not cfg.tester_field:
            raise HTTPException(status_code=400, detail="Поле 'Тестировщик' не настроено в конфиге")
        fields[cfg.tester_field] = {"accountId": body.tester_account_id}

    if body.responsible_account_id is not None:
        if not cfg.responsible_field:
            raise HTTPException(status_code=400, detail="Поле 'Аналитик' не настроено в конфиге")
        fields[cfg.responsible_field] = {"accountId": body.responsible_account_id}

    if not fields:
        return

    try:
        client.put(f"/rest/api/3/issue/{key}", json={"fields": fields})
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/standup/submit", response_model=list[StandupSubmitResult],
    dependencies=[Depends(get_jira_client)],
)
def submit_standup(
    body: StandupSubmitRequest,
    _user: models.User = Depends(require_lead),
):
    """Записать результаты стендапа: для задач с push_to_jira=True добавить комментарий в Jira."""
    results: list[StandupSubmitResult] = []

    for upd in body.updates:
        if not upd.push_to_jira:
            results.append(StandupSubmitResult(key=upd.key, bucket=upd.bucket, pushed=False))
            continue

        lines = [
            f"Статус на {body.standup_date} по итогу StandUp",
            f"Исполнитель: {upd.owner_file_name}",
            f"Фаза: {upd.bucket}",
            f"Ожидаемый статус: {upd.status}",
        ]
        if upd.comment.strip():
            lines.append(f"Комментарий: {upd.comment.strip()}")

        comment_body = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": line}]}
                    for line in lines
                ],
            }
        }

        try:
            client.post(f"/rest/api/3/issue/{upd.key}/comment", json=comment_body)
            results.append(StandupSubmitResult(key=upd.key, bucket=upd.bucket, pushed=True))
        except JiraError as e:
            results.append(StandupSubmitResult(
                key=upd.key, bucket=upd.bucket, pushed=False, error=str(e),
            ))

    return results


@router.get(
    "/users/search", response_model=list[JiraUserOut],
    dependencies=[Depends(get_jira_client)],
)
def search_users(
    q: str = Query(..., min_length=1, description="Запрос — имя или email"),
    _user: models.User = Depends(require_lead),
):
    """До 20 пользователей в Jira по подстроке имени или email."""
    try:
        data = client.get("/rest/api/3/user/search", params={"query": q, "maxResults": 20})
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not isinstance(data, list):
        return []

    return [
        JiraUserOut(
            account_id=u.get("accountId", ""),
            display_name=u.get("displayName", ""),
            email=u.get("emailAddress"),
            avatar_url=(u.get("avatarUrls") or {}).get("24x24"),
        )
        for u in data
        if isinstance(u, dict) and u.get("active") is not False
    ]
