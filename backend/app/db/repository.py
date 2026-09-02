"""Репозиторий конфига: CRUD-операции через SQLAlchemy.

Фаза 2.8: добавлен Person, team_member ссылается на person_id.
Источник данных о человеке — Person (jira_account_id, jira_name, file_name),
старые поля в team_members оставлены для совместимости и заполняются из Person.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models, people_repository


_eager_config = [
    selectinload(models.Config.team_members)
        .selectinload(models.TeamMember.person),
    selectinload(models.Config.team_members)
        .selectinload(models.TeamMember.pseudo_tasks),
    selectinload(models.Config.boards),
    selectinload(models.Config.components),
    selectinload(models.Config.status_priorities),
    selectinload(models.Config.role_hours_fields),
    selectinload(models.Config.roles),
    selectinload(models.Config.role_status_buckets),
    selectinload(models.Config.role_status_default_hours),
    selectinload(models.Config.pseudo_tasks),
    selectinload(models.Config.terminal_statuses),
    selectinload(models.Config.directions),
    selectinload(models.Config.vacations),
]


def list_configs(db: Session) -> list[models.Config]:
    return list(db.scalars(select(models.Config).options(*_eager_config)).all())


def list_configs_for_user(db: Session, owner_user_id: int) -> list[models.Config]:
    return list(db.scalars(
        select(models.Config)
        .where(models.Config.owner_user_id == owner_user_id)
        .order_by(models.Config.id)
        .options(*_eager_config)
    ).all())


def get_config(db: Session, config_id: int) -> models.Config | None:
    return db.scalar(
        select(models.Config).where(models.Config.id == config_id).options(*_eager_config)
    )


def get_user_config_by_name(db: Session, owner_user_id: int, name: str) -> models.Config | None:
    return db.scalar(
        select(models.Config)
        .where(models.Config.owner_user_id == owner_user_id,
               models.Config.name == name)
        .options(*_eager_config)
    )


# -------------------- Перезапись коллекций --------------------

def _replace_collection(db: Session, collection, items, build) -> None:
    """Полная перезапись relationship-коллекции: clear → flush → append.

    `build(i, item)` строит ORM-объект по элементу и его позиции. flush между
    clear и append обязателен — иначе delete-orphan может сработать после
    insert и снести только что добавленные строки с совпадающими uq-ключами.
    """
    collection.clear()
    db.flush()
    for i, item in enumerate(items):
        collection.append(build(i, item))

def get_global_salaries(db: Session, jira_account_ids: list[str] | None = None) -> dict[str, int]:
    """Оклады глобальны (не привязаны к конфигу) — один и тот же человек может иметь
    несколько записей TeamMember в разных конфигах с разным сохранённым окладом.

    Правило (единственное — раньше было продублировано с разной логикой в
    api/admin.py и api/epic.py и давало разные цифры для одного человека):
    берём МАКСИМАЛЬНЫЙ положительный salary среди всех записей на jira_account_id.

    jira_account_ids=None → по всем TeamMember в системе (для админ-таблицы окладов).
    """
    query = select(models.TeamMember)
    if jira_account_ids is not None:
        if not jira_account_ids:
            return {}
        query = query.where(models.TeamMember.jira_account_id.in_(jira_account_ids))
    result: dict[str, int] = {}
    for tm in db.execute(query).scalars():
        if tm.salary and tm.salary > 0:
            if tm.jira_account_id not in result or tm.salary > result[tm.jira_account_id]:
                result[tm.jira_account_id] = tm.salary
    return result


def upsert_team_members(db: Session, config: models.Config, items: list[dict]) -> None:
    """items: список dict с jira_account_id, jira_name, file_name, role, sort_order.

    Под капотом находим/создаём Person в справочнике пользователя.
    Существующие TeamMember обновляются на месте (ID сохраняется), чтобы не
    инвалидировать FK в pseudo_tasks. Только удалённые из списка — удаляются.
    """
    existing = {tm.jira_account_id: tm for tm in config.team_members}
    new_acc_ids = {item["jira_account_id"] for item in items}

    # Удаляем тех, кого убрали из команды
    for acc_id in list(existing):
        if acc_id not in new_acc_ids:
            config.team_members.remove(existing.pop(acc_id))
    db.flush()

    owner_id = config.owner_user_id
    for i, item in enumerate(items):
        acc_id = item["jira_account_id"]
        person = None
        if owner_id is not None:
            person = people_repository.get_or_create_person(
                db, owner_id,
                jira_account_id=acc_id,
                jira_name=item["jira_name"],
                file_name=item["file_name"],
            )

        if acc_id in existing:
            tm = existing[acc_id]
            tm.person_id = person.id if person else None
            tm.jira_name = item["jira_name"]
            tm.file_name = item["file_name"]
            tm.role = item.get("role", "analyst")
            tm.sort_order = item.get("sort_order", i)
            # salary — глобальное поле, управляется через /admin/salaries
            # (см. get_global_salaries), а не через это (per-конфиг) сохранение
            # команды. TeamMemberIn его не присылает вовсе — раньше `item.get
            # ("salary") or None` из-за этого безусловно обнулял уже
            # выставленный оклад при КАЖДОМ сохранении Settings → Team.
            # Трогаем salary только если он явно присутствует во входном dict.
            if "salary" in item:
                tm.salary = item["salary"] or None
        else:
            config.team_members.append(
                models.TeamMember(
                    person_id=person.id if person else None,
                    jira_account_id=acc_id,
                    jira_name=item["jira_name"],
                    file_name=item["file_name"],
                    role=item.get("role", "analyst"),
                    sort_order=item.get("sort_order", i),
                    salary=item.get("salary") or None,
                )
            )


def upsert_boards(db: Session, config: models.Config, items: list[dict]) -> None:
    _replace_collection(db, config.boards, items, lambda i, item: models.ConfigBoard(
        name=item["name"], jira_board_id=item["jira_board_id"],
    ))


def upsert_components(db: Session, config: models.Config, items: list[str]) -> None:
    _replace_collection(db, config.components, items,
                        lambda i, name: models.ConfigComponent(name=name))


def upsert_status_priorities(db: Session, config: models.Config,
                              items: dict[str, int]) -> None:
    _replace_collection(db, config.status_priorities, items.items(),
                        lambda i, kv: models.StatusPriority(jira_status=kv[0], priority=kv[1]))


def upsert_role_hours_fields(db: Session, config: models.Config,
                              items: dict[str, str]) -> None:
    _replace_collection(db, config.role_hours_fields, items.items(),
                        lambda i, kv: models.RoleHoursField(role=kv[0], customfield_id=kv[1]))


def upsert_roles(db: Session, config: models.Config, items: list[dict]) -> None:
    _replace_collection(db, config.roles, items, lambda i, item: models.Role(
        name=item["name"],
        display_name=item["display_name"],
        enabled=item.get("enabled", True),
        is_lead=item.get("is_lead", False),
        sort_order=item.get("sort_order", i),
    ))


def upsert_role_status_buckets(db: Session, config: models.Config,
                                items: list[dict]) -> None:
    _replace_collection(db, config.role_status_buckets, items,
                        lambda i, item: models.RoleStatusBucket(
                            role=item["role"],
                            jira_status=item["jira_status"],
                            bucket=item["bucket"],
                        ))


def upsert_role_status_default_hours(db: Session, config: models.Config,
                                      items: list[dict]) -> None:
    _replace_collection(db, config.role_status_default_hours, items,
                        lambda i, item: models.RoleStatusDefaultHours(
                            role=item["role"],
                            jira_status=item["jira_status"],
                            hours=item["hours"],
                        ))


def upsert_pseudo_tasks(db: Session, config: models.Config,
                        items: list[dict]) -> None:
    _replace_collection(db, config.pseudo_tasks, items, lambda i, item: models.PseudoTask(
        member_id=item["member_id"],
        name=item["name"],
        bucket=item["bucket"],
        hours=item["hours"],
        recurring=item.get("recurring", False),
        target_sprint_num=item.get("target_sprint_num"),
    ))


def upsert_directions(db: Session, config: models.Config,
                      items: list[dict]) -> None:
    _replace_collection(db, config.directions, items, lambda i, item: models.ConfigDirection(
        name=item["name"],
        labels=item.get("labels", []),
        work_types=item.get("work_types", []),
        role_overrides=item.get("role_overrides") or {},
        designer_id=item.get("designer_id") or None,
    ))


def upsert_terminal_statuses(db: Session, config: models.Config,
                              items: list[str]) -> None:
    _replace_collection(db, config.terminal_statuses, items,
                        lambda i, status: models.TerminalStatus(jira_status=status, sort_order=i))


# -------------------- Обновление конфига --------------------

def update_config(db: Session, config_id: int, data: dict) -> models.Config | None:
    config = get_config(db, config_id)
    if not config:
        return None

    for field in ("name", "project_key", "sprint_field", "responsible_field",
                  "hours_per_person", "default_task_hours",
                  "leader_hours", "leader_management_enabled", "developer_field",
                  "designer_field", "tester_field", "jira_base_url", "jira_email",
                  "telegram_chat_id", "telegram_daily_enabled", "telegram_daily_time",
                  "ai_provider"):
        if field in data:
            setattr(config, field, data[field])

    for data_key, attr in (("jira_api_token", "jira_api_token_enc"),
                           ("telegram_bot_token", "telegram_bot_token_enc"),
                           ("anthropic_api_key", "anthropic_api_key_enc"),
                           ("deepseek_api_key", "deepseek_api_key_enc")):
        if data_key in data:
            token = data[data_key]
            if token:
                from app.core.security import encrypt_secret
                setattr(config, attr, encrypt_secret(token))
            else:
                setattr(config, attr, "")

    if "team" in data:
        items = [
            {
                "jira_account_id": acc_id,
                "jira_name": info["jira_name"],
                "file_name": info["file_name"],
                "role": info.get("role", "analyst"),
                "salary": info.get("salary") or None,
            }
            for acc_id, info in data["team"].items()
        ]
        upsert_team_members(db, config, items)

    if "boards" in data:
        upsert_boards(db, config, [
            {"name": name, "jira_board_id": bid}
            for name, bid in data["boards"].items()
        ])
    if "extra_components" in data:
        upsert_components(db, config, data["extra_components"])
    if "status_priority" in data:
        upsert_status_priorities(db, config, data["status_priority"])
    if "role_hours_fields" in data:
        upsert_role_hours_fields(db, config, data["role_hours_fields"])

    if "roles" in data:
        upsert_roles(db, config, data["roles"])
    if "role_status_buckets" in data:
        upsert_role_status_buckets(db, config, data["role_status_buckets"])
    if "role_status_default_hours" in data:
        upsert_role_status_default_hours(db, config, data["role_status_default_hours"])
    if "pseudo_tasks" in data:
        upsert_pseudo_tasks(db, config, data["pseudo_tasks"])
    if "terminal_statuses" in data:
        upsert_terminal_statuses(db, config, data["terminal_statuses"])
    if "directions" in data:
        upsert_directions(db, config, data["directions"])

    db.commit()
    db.refresh(config)
    return config


# -------------------- Преобразование в dict --------------------

def model_to_sprint_config_dict(config: models.Config) -> dict:
    """ORM → dict в формате, ожидаемом сервисами и бизнес-логикой.

    Источник правды о человеке — Person (если есть). Если person_id NULL —
    fallback на старые поля в team_member.
    """
    team: dict = {}
    for tm in sorted(config.team_members, key=lambda m: m.sort_order):
        if tm.person is not None:
            acc_id = tm.person.jira_account_id
            jira_name = tm.person.jira_name
            file_name = tm.person.file_name
        else:
            acc_id = tm.jira_account_id
            jira_name = tm.jira_name
            file_name = tm.file_name
        team[acc_id] = {
            "jira_name": jira_name,
            "file_name": file_name,
            "role": tm.role,
            "id": tm.id,
            "person_id": tm.person_id,
            "salary": tm.salary or 0,
        }

    return {
        "project_key": config.project_key,
        "sprint_field": config.sprint_field,
        "responsible_field": config.responsible_field,
        "hours_per_person": config.hours_per_person,
        "default_task_hours": config.default_task_hours,
        "leader_hours": config.leader_hours,
        "leader_management_enabled": config.leader_management_enabled,
        "developer_field": config.developer_field or "",
        "designer_field": config.designer_field or "",
        "tester_field": config.tester_field or "",
        "team": team,
        "boards": {b.name: b.jira_board_id for b in config.boards},
        "extra_components": [c.name for c in config.components],
        "status_priority": {sp.jira_status: sp.priority for sp in config.status_priorities},
        "role_hours_fields": {rh.role: rh.customfield_id for rh in config.role_hours_fields},
        "roles": [
            {
                "name": r.name, "display_name": r.display_name,
                "enabled": r.enabled, "is_lead": r.is_lead,
                "sort_order": r.sort_order,
            }
            for r in sorted(config.roles, key=lambda x: x.sort_order)
        ],
        "role_status_buckets": [
            {"role": rsb.role, "jira_status": rsb.jira_status, "bucket": rsb.bucket}
            for rsb in config.role_status_buckets
        ],
        "role_status_default_hours": [
            {"role": rsdh.role, "jira_status": rsdh.jira_status, "hours": rsdh.hours}
            for rsdh in config.role_status_default_hours
        ],
        "pseudo_tasks": [
            {
                "member_id": pt.member_id,
                "name": pt.name,
                "bucket": pt.bucket,
                "hours": pt.hours,
                "recurring": pt.recurring,
                "target_sprint_num": pt.target_sprint_num,
            }
            for pt in config.pseudo_tasks
        ],
        "terminal_statuses": [
            ts.jira_status
            for ts in sorted(config.terminal_statuses, key=lambda x: x.sort_order)
        ],
        "directions": [
            {
                "name": d.name,
                "labels": d.labels,
                "work_types": d.work_types,
                "role_overrides": d.role_overrides or {},
                "designer_id":  d.designer_id or "",
            }
            for d in config.directions
        ],
        "vacations": vacations_to_dicts(config.vacations),
    }


# -------------------- Vacation CRUD --------------------

def vacations_to_dicts(vacations) -> list[dict]:
    """Преобразовать список EmployeeVacation → формат для compute_gantt_schedule."""
    return [
        {
            "owner_id": v.jira_account_id,
            "display_name": v.display_name,
            "start_date": v.start_date,
            "end_date": v.end_date,
        }
        for v in vacations
    ]


def list_vacations(db: Session, config_id: int) -> list[models.EmployeeVacation]:
    return list(db.scalars(
        select(models.EmployeeVacation)
        .where(models.EmployeeVacation.config_id == config_id)
        .order_by(models.EmployeeVacation.jira_account_id, models.EmployeeVacation.start_date)
    ).all())


def add_vacation(
    db: Session,
    config_id: int,
    jira_account_id: str,
    display_name: str,
    start_date: str,
    end_date: str,
) -> models.EmployeeVacation:
    vac = models.EmployeeVacation(
        config_id=config_id,
        jira_account_id=jira_account_id,
        display_name=display_name,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(vac)
    db.flush()
    return vac


def delete_vacation(db: Session, vacation_id: int, config_id: int) -> bool:
    vac = db.scalar(
        select(models.EmployeeVacation)
        .where(models.EmployeeVacation.id == vacation_id,
               models.EmployeeVacation.config_id == config_id)
    )
    if not vac:
        return False
    db.delete(vac)
    db.flush()
    return True


# -------------------- Epic dependencies --------------------

def list_epic_dependencies(
    db: Session, config_id: int, epic_key: str,
) -> list[models.EpicTaskDependency]:
    return list(db.scalars(
        select(models.EpicTaskDependency)
        .where(
            models.EpicTaskDependency.config_id == config_id,
            models.EpicTaskDependency.epic_key == epic_key,
        )
    ).all())


def list_epic_dependencies_for_keys(
    db: Session, config_id: int, epic_keys: list[str],
) -> list[models.EpicTaskDependency]:
    """Зависимости под любым из перечисленных epic_key (объединение нескольких
    scope-ключей — см. _dependency_scope_keys в api/epic.py)."""
    if not epic_keys:
        return []
    return list(db.scalars(
        select(models.EpicTaskDependency)
        .where(
            models.EpicTaskDependency.config_id == config_id,
            models.EpicTaskDependency.epic_key.in_(epic_keys),
        )
    ).all())


def _find_epic_dependency(
    db: Session, config_id: int, epic_key: str, from_key: str, to_key: str,
    from_bucket: str, to_bucket: str,
) -> models.EpicTaskDependency | None:
    return db.scalar(
        select(models.EpicTaskDependency)
        .where(
            models.EpicTaskDependency.config_id == config_id,
            models.EpicTaskDependency.epic_key == epic_key,
            models.EpicTaskDependency.from_key == from_key,
            models.EpicTaskDependency.to_key == to_key,
            models.EpicTaskDependency.from_bucket == from_bucket,
            models.EpicTaskDependency.to_bucket == to_bucket,
        )
    )


def add_epic_dependency(
    db: Session, config_id: int, epic_key: str, from_key: str, to_key: str,
    from_bucket: str = "", to_bucket: str = "",
) -> list[models.EpicTaskDependency]:
    existing = _find_epic_dependency(
        db, config_id, epic_key, from_key, to_key, from_bucket, to_bucket,
    )
    if not existing:
        dep = models.EpicTaskDependency(
            config_id=config_id, epic_key=epic_key, from_key=from_key, to_key=to_key,
            from_bucket=from_bucket, to_bucket=to_bucket,
        )
        db.add(dep)
        db.flush()
    return list_epic_dependencies(db, config_id, epic_key)


def remove_epic_dependency(
    db: Session, config_id: int, epic_key: str, from_key: str, to_key: str,
    from_bucket: str = "", to_bucket: str = "",
) -> None:
    dep = _find_epic_dependency(
        db, config_id, epic_key, from_key, to_key, from_bucket, to_bucket,
    )
    if dep:
        db.delete(dep)
        db.flush()


# -------------------- Employee root tasks --------------------

def list_root_tasks(
    db: Session, config_id: int, epic_key: str,
) -> list[models.EmployeeRootTask]:
    return list(db.scalars(
        select(models.EmployeeRootTask)
        .where(
            models.EmployeeRootTask.config_id == config_id,
            models.EmployeeRootTask.epic_key == epic_key,
        )
    ).all())


def _find_root_task(
    db: Session, config_id: int, epic_key: str, owner_id: str,
) -> models.EmployeeRootTask | None:
    return db.scalar(
        select(models.EmployeeRootTask)
        .where(
            models.EmployeeRootTask.config_id == config_id,
            models.EmployeeRootTask.epic_key == epic_key,
            models.EmployeeRootTask.owner_id == owner_id,
        )
    )


def set_root_task(
    db: Session, config_id: int, epic_key: str, owner_id: str, task_key: str,
) -> list[models.EmployeeRootTask]:
    existing = _find_root_task(db, config_id, epic_key, owner_id)
    if existing:
        existing.task_key = task_key
    else:
        db.add(models.EmployeeRootTask(
            config_id=config_id, epic_key=epic_key, owner_id=owner_id, task_key=task_key,
        ))
    db.flush()
    return list_root_tasks(db, config_id, epic_key)


def remove_root_task(
    db: Session, config_id: int, epic_key: str, owner_id: str,
) -> None:
    existing = _find_root_task(db, config_id, epic_key, owner_id)
    if existing:
        db.delete(existing)
        db.flush()


def cleanup_stale_root_tasks(
    db: Session, config_id: int, epic_key: str,
    valid_keys: set[str], terminal_keys: set[str],
) -> None:
    """Снять якорь, если задача исчезла из выборки или стала терминальной (п.1.3 ТЗ)."""
    for rt in list_root_tasks(db, config_id, epic_key):
        if rt.task_key not in valid_keys or rt.task_key in terminal_keys:
            db.delete(rt)
    db.flush()


# -------------------- Task details ("Детализация") --------------------

def list_task_details(db: Session, config_id: int) -> list[models.TaskDetail]:
    return list(db.scalars(
        select(models.TaskDetail).where(models.TaskDetail.config_id == config_id)
    ).all())


def _find_task_detail(db: Session, config_id: int, task_key: str) -> models.TaskDetail | None:
    return db.scalar(
        select(models.TaskDetail).where(
            models.TaskDetail.config_id == config_id,
            models.TaskDetail.task_key == task_key,
        )
    )


def set_task_detail(db: Session, config_id: int, task_key: str, detail: str) -> models.TaskDetail | None:
    """Пустая строка удаляет запись (задача возвращается в "без темы")."""
    existing = _find_task_detail(db, config_id, task_key)
    detail = detail.strip()
    if not detail:
        if existing:
            db.delete(existing)
            db.flush()
        return None
    if existing:
        existing.detail = detail
    else:
        existing = models.TaskDetail(config_id=config_id, task_key=task_key, detail=detail)
        db.add(existing)
    db.flush()
    return existing


# -------------------- Epic plans (ручной план старта/окончания) --------------------

def list_epic_plans(db: Session, config_id: int) -> list[models.EpicPlan]:
    return list(db.scalars(
        select(models.EpicPlan).where(models.EpicPlan.config_id == config_id)
    ).all())


def _find_epic_plan(db: Session, config_id: int, epic_key: str) -> models.EpicPlan | None:
    return db.scalar(
        select(models.EpicPlan).where(
            models.EpicPlan.config_id == config_id,
            models.EpicPlan.epic_key == epic_key,
        )
    )


def set_epic_plan(
    db: Session, config_id: int, epic_key: str, planned_start: str, planned_end: str,
) -> models.EpicPlan | None:
    """Оба поля пустые — удаляет запись (эпик возвращается к чисто фактическим датам)."""
    existing = _find_epic_plan(db, config_id, epic_key)
    planned_start, planned_end = planned_start.strip(), planned_end.strip()
    if not planned_start and not planned_end:
        if existing:
            db.delete(existing)
            db.flush()
        return None
    if existing:
        existing.planned_start = planned_start
        existing.planned_end = planned_end
    else:
        existing = models.EpicPlan(
            config_id=config_id, epic_key=epic_key,
            planned_start=planned_start, planned_end=planned_end,
        )
        db.add(existing)
    db.flush()
    return existing


# -------------------- Epic forecast snapshots --------------------

def upsert_epic_snapshot(
    db: Session,
    config_id: int,
    epic_key: str,
    captured_date: str,
    start_date: str,
    hours_per_day: float,
    completion_date: str | None,
    total_issues: int,
    done_issues: int,
    remaining_work_items: int,
    total_planned_hours: float,
) -> models.EpicForecastSnapshot:
    snap = db.scalar(
        select(models.EpicForecastSnapshot)
        .where(
            models.EpicForecastSnapshot.config_id == config_id,
            models.EpicForecastSnapshot.epic_key == epic_key,
            models.EpicForecastSnapshot.captured_date == captured_date,
        )
    )
    if snap:
        if snap.is_pinned:
            return snap
        snap.start_date = start_date
        snap.hours_per_day = hours_per_day
        snap.completion_date = completion_date
        snap.total_issues = total_issues
        snap.done_issues = done_issues
        snap.remaining_work_items = remaining_work_items
        snap.total_planned_hours = total_planned_hours
    else:
        snap = models.EpicForecastSnapshot(
            config_id=config_id,
            epic_key=epic_key,
            captured_date=captured_date,
            start_date=start_date,
            hours_per_day=hours_per_day,
            completion_date=completion_date,
            total_issues=total_issues,
            done_issues=done_issues,
            remaining_work_items=remaining_work_items,
            total_planned_hours=total_planned_hours,
        )
        db.add(snap)
    db.flush()
    return snap


def pin_epic_snapshot(
    db: Session, snapshot_id: int, config_id: int, pinned: bool,
) -> models.EpicForecastSnapshot | None:
    snap = db.scalar(
        select(models.EpicForecastSnapshot)
        .where(
            models.EpicForecastSnapshot.id == snapshot_id,
            models.EpicForecastSnapshot.config_id == config_id,
        )
    )
    if not snap:
        return None
    snap.is_pinned = pinned
    db.flush()
    return snap


def list_epic_snapshots(
    db: Session, config_id: int, epic_key: str,
) -> list[models.EpicForecastSnapshot]:
    return list(db.scalars(
        select(models.EpicForecastSnapshot)
        .where(
            models.EpicForecastSnapshot.config_id == config_id,
            models.EpicForecastSnapshot.epic_key == epic_key,
        )
        .order_by(models.EpicForecastSnapshot.captured_date)
    ).all())


def delete_epic_snapshot(
    db: Session, snapshot_id: int, config_id: int,
) -> bool:
    snap = db.scalar(
        select(models.EpicForecastSnapshot)
        .where(
            models.EpicForecastSnapshot.id == snapshot_id,
            models.EpicForecastSnapshot.config_id == config_id,
        )
    )
    if not snap:
        return False
    db.delete(snap)
    db.flush()
    return True


# -------------------- Снимки Ганта эпика (прогноз) --------------------
# Тот же механизм, что и sprint_gantt_snapshots для спринтов (см. sprints_repository),
# но привязан к (config_id, epic_key) вместо sprint_id.

def create_epic_gantt_snapshot(
    db: Session, config_id: int, epic_key: str, gantt_start: str, hours_per_day: float,
    gantt_items: list[dict], label: str | None = None,
) -> models.SprintGanttSnapshot:
    snap = models.SprintGanttSnapshot(
        config_id=config_id, epic_key=epic_key, gantt_start=gantt_start,
        hours_per_day=hours_per_day, gantt_items=gantt_items, label=label,
    )
    db.add(snap)
    db.flush()
    return snap


def list_epic_gantt_snapshots(
    db: Session, config_id: int, epic_key: str,
) -> list[models.SprintGanttSnapshot]:
    return list(db.scalars(
        select(models.SprintGanttSnapshot)
        .where(
            models.SprintGanttSnapshot.config_id == config_id,
            models.SprintGanttSnapshot.epic_key == epic_key,
        )
        .order_by(models.SprintGanttSnapshot.captured_at.desc())
    ).all())


def get_epic_gantt_snapshot(
    db: Session, config_id: int, epic_key: str, snapshot_id: int,
) -> models.SprintGanttSnapshot | None:
    return db.scalar(
        select(models.SprintGanttSnapshot)
        .where(
            models.SprintGanttSnapshot.id == snapshot_id,
            models.SprintGanttSnapshot.config_id == config_id,
            models.SprintGanttSnapshot.epic_key == epic_key,
        )
    )


def delete_epic_gantt_snapshot(
    db: Session, config_id: int, epic_key: str, snapshot_id: int,
) -> bool:
    snap = get_epic_gantt_snapshot(db, config_id, epic_key, snapshot_id)
    if not snap:
        return False
    db.delete(snap)
    db.flush()
    return True
