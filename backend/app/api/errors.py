"""Глобальный обработчик ошибок целостности БД.

Превращает sqlalchemy.exc.IntegrityError в понятные HTTP 400 на русском.
Подключается в main.py через app.add_exception_handler.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


# Маппинг известных constraint-имён → человеческое сообщение.
# При добавлении новых уникальных ключей в модель — добавляй сюда строку.
_CONSTRAINT_MESSAGES: dict[str, str] = {
    "uq_board_config_jiraid":
        "Эта Jira-доска уже добавлена в конфиг. Каждый jira_board_id может быть только одним.",
    "uq_component_config_name":
        "Этот компонент уже добавлен в конфиг.",
    "uq_role_config_name":
        "Роль с таким name уже есть в конфиге.",
    "uq_rsb_config_role_status":
        "Этот статус уже задан для этой роли. Снимите старую запись или используйте другой статус.",
    "uq_rsdh_config_role_status":
        "Дефолтные часы для этой пары (роль, статус) уже заданы.",
    "uq_statusprio_config_status":
        "Приоритет для этого статуса уже задан.",
    "uq_rolehours_config_role":
        "Поле часов для этой роли уже задано.",
    "uq_team_config_person_role":
        "Этот человек уже есть в команде с такой ролью.",
    "uq_termstatus_config_status":
        "Этот терминальный статус уже добавлен.",
    "uq_config_owner_name":
        "У тебя уже есть конфиг с таким именем. Выбери другое.",
    "uq_people_owner_account":
        "Этот пользователь Jira уже есть в твоём справочнике.",
    "uq_users_email":
        "Пользователь с таким email уже существует.",
}


def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Расшифровать IntegrityError → 400 с понятным сообщением.

    Если constraint распознан — выдаём подготовленное сообщение.
    Иначе — общее «нарушение целостности данных», но с reason из БД.
    """
    msg = "Нарушение целостности данных."

    # У psycopg/postgres detail обычно содержит имя constraint-а.
    # Пройдём по списку известных и найдём.
    text = str(exc.orig) if exc.orig else str(exc)
    for cname, hint in _CONSTRAINT_MESSAGES.items():
        if cname in text:
            msg = hint
            break

    return JSONResponse(status_code=400, content={"detail": msg})
