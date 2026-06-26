"""Глобальный обработчик ошибок целостности БД.

Превращает sqlalchemy.exc.IntegrityError в понятные HTTP 400 на русском.
Подключается в main.py через app.add_exception_handler.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.i18n import get_lang, make_translator

# Маппинг известных constraint-имён → человеческое сообщение.
# При добавлении новых уникальных ключей в модель — добавляй сюда запись.
_CONSTRAINT_MESSAGES: dict[str, dict[str, str]] = {
    "uq_board_config_jiraid": {
        "ru": "Эта Jira-доска уже добавлена в конфиг. Каждый jira_board_id может быть только одним.",
        "en": "This Jira board is already added to the config. Each jira_board_id can only be used once.",
    },
    "uq_component_config_name": {
        "ru": "Этот компонент уже добавлен в конфиг.",
        "en": "This component is already added to the config.",
    },
    "uq_role_config_name": {
        "ru": "Роль с таким name уже есть в конфиге.",
        "en": "A role with this name already exists in the config.",
    },
    "uq_rsb_config_role_status": {
        "ru": "Этот статус уже задан для этой роли. Снимите старую запись или используйте другой статус.",
        "en": "This status is already set for this role. Remove the old entry or use a different status.",
    },
    "uq_rsdh_config_role_status": {
        "ru": "Дефолтные часы для этой пары (роль, статус) уже заданы.",
        "en": "Default hours for this (role, status) pair are already set.",
    },
    "uq_statusprio_config_status": {
        "ru": "Приоритет для этого статуса уже задан.",
        "en": "Priority for this status is already set.",
    },
    "uq_rolehours_config_role": {
        "ru": "Поле часов для этой роли уже задано.",
        "en": "Hours field for this role is already set.",
    },
    "uq_team_config_person_role": {
        "ru": "Этот человек уже есть в команде с такой ролью.",
        "en": "This person already has this role on the team.",
    },
    "uq_termstatus_config_status": {
        "ru": "Этот терминальный статус уже добавлен.",
        "en": "This terminal status is already added.",
    },
    "uq_config_owner_name": {
        "ru": "У тебя уже есть конфиг с таким именем. Выбери другое.",
        "en": "You already have a config with this name. Choose another one.",
    },
    "uq_people_owner_account": {
        "ru": "Этот пользователь Jira уже есть в твоём справочнике.",
        "en": "This Jira user is already in your directory.",
    },
    "uq_users_email": {
        "ru": "Пользователь с таким email уже существует.",
        "en": "A user with this email already exists.",
    },
}
_t = make_translator(_CONSTRAINT_MESSAGES)
_GENERIC = {"ru": "Нарушение целостности данных.", "en": "Data integrity violation."}


def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Расшифровать IntegrityError → 400 с понятным сообщением.

    Если constraint распознан — выдаём подготовленное сообщение.
    Иначе — общее «нарушение целостности данных», но с reason из БД.
    """
    lang = get_lang(request)
    msg = _GENERIC.get(lang, _GENERIC["ru"])

    # У psycopg/postgres detail обычно содержит имя constraint-а.
    # Пройдём по списку известных и найдём.
    text = str(exc.orig) if exc.orig else str(exc)
    for cname in _CONSTRAINT_MESSAGES:
        if cname in text:
            msg = _t(cname, lang)
            break

    return JSONResponse(status_code=400, content={"detail": msg})
