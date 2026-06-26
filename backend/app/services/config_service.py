"""Config service — фаза 2.8: multi-config per lead.

Главные функции:
- list_user_configs — все конфиги lead-а.
- get_active_config — текущий рабочий конфиг (из users.active_config_id).
- ensure_active_config — создать первый при необходимости.
- create_empty_config / create_config_from — создать новый.
- delete_config — удалить с CASCADE.
- set_active_config — переключить.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.i18n import make_translator
from app.db import models, repository, users_repository
from app.db.repository import (
    upsert_directions, upsert_role_status_buckets, upsert_role_status_default_hours,
    upsert_roles, upsert_terminal_statuses,
)

_MSG: dict[str, dict[str, str]] = {
    "config_not_found_or_not_owned": {
        "ru": "Конфиг {id} не найден или вам не принадлежит",
        "en": "Config {id} not found or does not belong to you",
    },
    "config_name_empty": {
        "ru": "Имя конфига не может быть пустым",
        "en": "Config name cannot be empty",
    },
    "source_config_not_found": {
        "ru": "Исходный конфиг {id} не найден",
        "en": "Source config {id} not found",
    },
}
_t = make_translator(_MSG)


class ConfigServiceError(Exception):
    """Доменная ошибка операций над конфигами."""


# ---------- Дефолтные значения для нового пустого конфига ----------

_DEFAULT_ROLES = [
    ("analyst",        "Аналитик",       True,  False, 0),
    ("designer",       "Дизайнер",       False, False, 1),
    ("designer_lead",  "Лид дизайна",    False, True,  2),
    ("developer",      "Разработчик",    False, False, 3),
    ("developer_lead", "Лид разработки", False, True,  4),
]

_DEFAULT_ROLE_STATUS_BUCKETS = [
    ("analyst", "Создана", "Анализ"),
    ("analyst", "Новый", "Анализ"),
    ("analyst", "Анализ", "Анализ"),
    ("analyst", "В работе", "Анализ"),
    ("analyst", "Готов к разработке", "Тестирование"),
    ("analyst", "К разработке", "Тестирование"),
    ("analyst", "В разработке", "Тестирование"),
    ("analyst", "Код-ревью", "Тестирование"),
    ("analyst", "К тестированию", "Тестирование"),
    ("analyst", "Тестирование", "Тестирование"),
]

_DEFAULT_TERMINAL_STATUSES = [
    "Выполнено", "Завершено", "Перенесено на Prod", "Отменено",
]


# ---------- Списки и активный ----------

def list_user_configs(db: Session, user_id: int) -> list[models.Config]:
    return repository.list_configs_for_user(db, user_id)


def get_active_config(db: Session, user: models.User) -> models.Config | None:
    """Активный конфиг пользователя. None если у lead-а ещё нет ни одного."""
    if user.active_config_id:
        cfg = repository.get_config(db, user.active_config_id)
        if cfg and cfg.owner_user_id == user.id:
            return cfg
        # active_config_id указывает на чужой/удалённый — сбрасываем
        users_repository.set_active_config(db, user, None)

    # Берём первый по id из существующих
    configs = repository.list_configs_for_user(db, user.id)
    if not configs:
        return None
    first = configs[0]
    users_repository.set_active_config(db, user, first.id)
    return first


def ensure_active_config(db: Session, user: models.User) -> models.Config:
    """Активный конфиг; если нет ни одного — создать пустой 'Основной'."""
    cfg = get_active_config(db, user)
    if cfg:
        return cfg

    cfg = create_empty_config(db, user, name="Основной")
    users_repository.set_active_config(db, user, cfg.id)
    return cfg


def set_active_config(db: Session, user: models.User,
                       config_id: int, lang: str = "ru") -> models.Config:
    cfg = repository.get_config(db, config_id)
    if not cfg or cfg.owner_user_id != user.id:
        raise ConfigServiceError(_t("config_not_found_or_not_owned", lang, id=config_id))
    users_repository.set_active_config(db, user, config_id)
    return cfg


# ---------- Создание ----------

def _unique_name(db: Session, user_id: int, desired: str) -> str:
    """Сделать имя уникальным в рамках пользователя, добавляя суффикс."""
    base = desired
    suffix = 1
    while repository.get_user_config_by_name(db, user_id, base):
        suffix += 1
        base = f"{desired} ({suffix})"
    return base


def create_empty_config(db: Session, user: models.User, *, name: str, lang: str = "ru") -> models.Config:
    """Пустой конфиг с дефолтным набором ролей. Имя — уникально в рамках user."""
    if not name.strip():
        raise ConfigServiceError(_t("config_name_empty", lang))

    cfg_name = _unique_name(db, user.id, name.strip())

    cfg = models.Config(
        name=cfg_name,
        is_default=False,
        owner_user_id=user.id,
        project_key="",
        sprint_field="customfield_10018",
        responsible_field="customfield_10105",
        hours_per_person=80.0,
        default_task_hours=12.0,
        leader_hours=20.0,
        leader_management_enabled=True,
        developer_field="",
    )
    db.add(cfg)
    db.flush()

    upsert_roles(db, cfg, [
        {"name": n, "display_name": d, "enabled": e, "is_lead": l, "sort_order": o}
        for n, d, e, l, o in _DEFAULT_ROLES
    ])
    upsert_role_status_buckets(db, cfg, [
        {"role": r, "jira_status": s, "bucket": b}
        for r, s, b in _DEFAULT_ROLE_STATUS_BUCKETS
    ])
    upsert_role_status_default_hours(db, cfg, [
        {"role": "developer_lead", "jira_status": "Код-ревью", "hours": 1},
        {"role": "designer_lead",  "jira_status": "Дизайн-ревью", "hours": 1},
    ])
    upsert_terminal_statuses(db, cfg, _DEFAULT_TERMINAL_STATUSES)

    db.commit()
    db.refresh(cfg)
    return cfg


def create_config_from(db: Session, user: models.User, *,
                        source_config_id: int, name: str, lang: str = "ru") -> models.Config:
    """Создать новый конфиг копированием из source. Псевдо-задачи НЕ копируем."""
    source = repository.get_config(db, source_config_id)
    if not source:
        raise ConfigServiceError(_t("source_config_not_found", lang, id=source_config_id))

    if not name.strip():
        raise ConfigServiceError(_t("config_name_empty", lang))
    cfg_name = _unique_name(db, user.id, name.strip())

    src_dict = repository.model_to_sprint_config_dict(source)

    cfg = models.Config(
        name=cfg_name,
        is_default=False,
        owner_user_id=user.id,
        project_key=src_dict["project_key"],
        sprint_field=src_dict["sprint_field"],
        responsible_field=src_dict["responsible_field"],
        hours_per_person=src_dict["hours_per_person"],
        default_task_hours=src_dict["default_task_hours"],
        leader_hours=src_dict["leader_hours"],
        leader_management_enabled=src_dict["leader_management_enabled"],
        developer_field=src_dict.get("developer_field", ""),
    )
    db.add(cfg)
    db.flush()

    # Команда
    repository.upsert_team_members(db, cfg, [
        {
            "jira_account_id": acc_id,
            "jira_name": info["jira_name"],
            "file_name": info["file_name"],
            "role": info["role"],
        }
        for acc_id, info in src_dict["team"].items()
    ])
    repository.upsert_boards(db, cfg, [
        {"name": n, "jira_board_id": bid} for n, bid in src_dict["boards"].items()
    ])
    repository.upsert_components(db, cfg, src_dict["extra_components"])
    repository.upsert_status_priorities(db, cfg, src_dict["status_priority"])
    repository.upsert_role_hours_fields(db, cfg, src_dict["role_hours_fields"])
    upsert_roles(db, cfg, src_dict["roles"])
    upsert_role_status_buckets(db, cfg, src_dict["role_status_buckets"])
    upsert_role_status_default_hours(db, cfg, src_dict["role_status_default_hours"])
    upsert_terminal_statuses(db, cfg, src_dict["terminal_statuses"])
    upsert_directions(db, cfg, src_dict.get("directions", []))
    # ВНИМАНИЕ: pseudo_tasks НЕ копируем (договорённость).

    db.commit()
    db.refresh(cfg)
    return cfg


def delete_config(db: Session, user: models.User, config_id: int, lang: str = "ru") -> None:
    cfg = repository.get_config(db, config_id)
    if not cfg or cfg.owner_user_id != user.id:
        raise ConfigServiceError(_t("config_not_found_or_not_owned", lang, id=config_id))

    # Защита от удаления последнего конфига — не делаем, lead может остаться
    # без конфига. При следующем обращении ensure_active_config создаст ему
    # новый пустой "Основной".

    # Если этот конфиг активный — сбросим
    if user.active_config_id == config_id:
        users_repository.set_active_config(db, user, None)

    db.delete(cfg)
    db.commit()


# ---------- Обновление ----------

def update(db: Session, config_id: int, data: dict) -> models.Config | None:
    return repository.update_config(db, config_id, data)


# ---------- В DTO ----------

def to_out_dict(config: models.Config) -> dict:
    base = repository.model_to_sprint_config_dict(config)
    return {
        "id": config.id,
        "name": config.name,
        "is_default": config.is_default,
        "owner_user_id": config.owner_user_id,
        "jira_base_url": config.jira_base_url or "",
        "jira_email": config.jira_email or "",
        "jira_api_token_set": bool(config.jira_api_token_enc),
        "telegram_chat_id": config.telegram_chat_id or "",
        "telegram_daily_enabled": bool(config.telegram_daily_enabled),
        "telegram_daily_time": config.telegram_daily_time or "",
        "telegram_bot_token_set": bool(config.telegram_bot_token_enc),
        # Доступна ли отправка вообще: токен конфига ИЛИ глобальный .env.
        "telegram_bot_configured": bool(config.telegram_bot_token_enc) or bool(settings.telegram_bot_token),
        **base,
    }
