"""Схемы для Jira-эндпоинтов."""

from pydantic import BaseModel


class IssueFieldsUpdate(BaseModel):
    hours_analyst: float | None = None
    hours_tester: float | None = None
    hours_developer: float | None = None
    hours_designer: float | None = None
    developer_account_id: str | None = None
    designer_account_id: str | None = None
    tester_account_id: str | None = None
    responsible_account_id: str | None = None


class JiraUserOut(BaseModel):
    account_id: str
    display_name: str
    email: str | None
    avatar_url: str | None


class StandupTaskUpdate(BaseModel):
    key: str
    owner_file_name: str
    bucket: str
    status: str
    comment: str = ""
    push_to_jira: bool = False


class StandupSubmitRequest(BaseModel):
    standup_date: str   # "DD.MM.YYYY"
    updates: list[StandupTaskUpdate]


class StandupSubmitResult(BaseModel):
    key: str
    bucket: str
    pushed: bool
    error: str | None = None
