"""Jira: проверка подключения, поиск пользователей, обновление полей задач."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import current_config, get_jira_client, require_lead
from app.core.i18n import get_lang, make_translator
from app.db import models
from app.jira.client import JiraError, client
from app.schemas.jira import (
    IssueFieldsUpdate, JiraUserOut,
    StandupSubmitRequest, StandupSubmitResult,
)

router = APIRouter(prefix="/jira", tags=["jira"])

_MSG: dict[str, dict[str, str]] = {
    "field_not_configured": {
        "ru": "Поле '{label}' не настроено в конфиге",
        "en": "Field '{label}' is not configured",
    },
    "hours_analyst": {"ru": "Часы аналитика", "en": "Analyst hours"},
    "hours_tester": {"ru": "Часы тестера", "en": "Tester hours"},
    "hours_developer": {"ru": "Часы разработчика", "en": "Developer hours"},
    "hours_designer": {"ru": "Часы дизайнера", "en": "Designer hours"},
    "field_developer": {"ru": "Разработчик", "en": "Developer"},
    "field_designer": {"ru": "Дизайнер", "en": "Designer"},
    "field_tester": {"ru": "Тестировщик", "en": "Tester"},
    "field_analyst": {"ru": "Аналитик", "en": "Analyst"},
}
_t = make_translator(_MSG)


@router.get("/check", dependencies=[Depends(get_jira_client)])
def jira_check(lang: str = Depends(get_lang)):
    try:
        me = client.get("/rest/api/3/myself")
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))
    return {"display_name": me.get("displayName"), "email": me.get("emailAddress")}

# Поля часов: (атрибут тела запроса, ключ в role_hours_fields, ключ сообщения с человекочитаемым именем)
_HOURS_ROLE_FIELDS = [
    ("hours_analyst",   "analyst",  "hours_analyst"),
    ("hours_tester",    "tester",   "hours_tester"),
    ("hours_developer", "developer","hours_developer"),
    ("hours_designer",  "designer", "hours_designer"),
]


@router.patch("/issues/{key}/fields", status_code=204, dependencies=[Depends(get_jira_client)])
def update_issue_fields(
    key: str,
    body: IssueFieldsUpdate,
    config: models.Config = Depends(current_config),
    lang: str = Depends(get_lang),
):
    """Обновить поля задачи в Jira: часы ролей и/или разработчик."""
    from app.db import repository
    from app.sprint.config import from_dict
    cfg = from_dict(repository.model_to_sprint_config_dict(config))

    fields: dict = {}

    for attr, role_key, label_key in _HOURS_ROLE_FIELDS:
        value = getattr(body, attr)
        if value is None:
            continue
        fid = cfg.role_hours_fields.get(role_key)
        if not fid:
            raise HTTPException(
                status_code=400,
                detail=_t("field_not_configured", lang, label=_t(label_key, lang)),
            )
        fields[fid] = value

    if body.developer_account_id is not None:
        if not cfg.developer_field:
            raise HTTPException(
                status_code=400,
                detail=_t("field_not_configured", lang, label=_t("field_developer", lang)),
            )
        fields[cfg.developer_field] = {"accountId": body.developer_account_id}

    if body.designer_account_id is not None:
        if not cfg.designer_field:
            raise HTTPException(
                status_code=400,
                detail=_t("field_not_configured", lang, label=_t("field_designer", lang)),
            )
        fields[cfg.designer_field] = {"accountId": body.designer_account_id}

    if body.tester_account_id is not None:
        if not cfg.tester_field:
            raise HTTPException(
                status_code=400,
                detail=_t("field_not_configured", lang, label=_t("field_tester", lang)),
            )
        fields[cfg.tester_field] = {"accountId": body.tester_account_id}

    if body.responsible_account_id is not None:
        if not cfg.responsible_field:
            raise HTTPException(
                status_code=400,
                detail=_t("field_not_configured", lang, label=_t("field_analyst", lang)),
            )
        fields[cfg.responsible_field] = {"accountId": body.responsible_account_id}

    if not fields:
        return

    try:
        client.put(f"/rest/api/3/issue/{key}", json={"fields": fields})
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))


@router.post(
    "/standup/submit", response_model=list[StandupSubmitResult],
    dependencies=[Depends(get_jira_client)],
)
def submit_standup(
    body: StandupSubmitRequest,
    _user: models.User = Depends(require_lead),
    lang: str = Depends(get_lang),
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
                key=upd.key, bucket=upd.bucket, pushed=False, error=e.text(lang),
            ))

    return results


@router.get(
    "/users/search", response_model=list[JiraUserOut],
    dependencies=[Depends(get_jira_client)],
)
def search_users(
    q: str = Query(..., min_length=1, description="Запрос — имя или email"),
    _user: models.User = Depends(require_lead),
    lang: str = Depends(get_lang),
):
    """До 20 пользователей в Jira по подстроке имени или email."""
    try:
        data = client.get("/rest/api/3/user/search", params={"query": q, "maxResults": 20})
    except JiraError as e:
        raise HTTPException(status_code=502, detail=e.text(lang))

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
