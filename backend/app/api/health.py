"""Health-чек и проверка Jira."""

from fastapi import APIRouter, HTTPException

from app.jira.client import JiraError, client

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/jira/check")
def jira_check():
    try:
        me = client.get("/rest/api/3/myself")
    except JiraError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"display_name": me.get("displayName"), "email": me.get("emailAddress")}
