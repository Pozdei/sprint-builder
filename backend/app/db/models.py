"""SQLAlchemy-модели.

Фаза 2.10: добавлено поле Sprint.intrusions — JSON со списком "врывов"
(задач, которые появились в Jira-спринте после approve).
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# -------------------- Users --------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
    active_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("configs.id", ondelete="SET NULL"), nullable=True,
    )


# -------------------- People --------------------

class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "jira_account_id",
                         name="uq_people_owner_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    jira_account_id: Mapped[str] = mapped_column(String(100))
    jira_name: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(100))


# -------------------- Config --------------------

class Config(Base):
    __tablename__ = "configs"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_config_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
    )

    project_key: Mapped[str] = mapped_column(String(50))
    sprint_field: Mapped[str] = mapped_column(String(50))
    responsible_field: Mapped[str] = mapped_column(String(50))
    hours_per_person: Mapped[float] = mapped_column(Float)
    default_task_hours: Mapped[float] = mapped_column(Float)

    leader_hours: Mapped[float] = mapped_column(Float, default=20.0)
    leader_management_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Поле Jira «Разработчик» — customfield_XXXXX; пустая строка = не задано
    developer_field: Mapped[str] = mapped_column(String(50), default="")
    # Поле Jira «Дизайнер» — customfield_XXXXX; пустая строка = не задано
    designer_field: Mapped[str] = mapped_column(String(50), default="")
    # Поле Jira «Тестировщик» — customfield_XXXXX; пустая строка = не задано
    tester_field: Mapped[str] = mapped_column(String(50), default="")

    # Подключение к Jira для этого конфига; пусто = берём из .env (settings).
    # Действует только если все три поля заданы — частичного смешивания нет.
    jira_base_url: Mapped[str] = mapped_column(String(200), default="")
    jira_email: Mapped[str] = mapped_column(String(200), default="")
    jira_api_token_enc: Mapped[str] = mapped_column(String(500), default="")

    # Telegram-дайджест «задачи на сегодня» по последнему утверждённому спринту.
    # Токен бота резолвится так: токен конфига (если задан) → глобальный settings.telegram_bot_token.
    telegram_bot_token_enc: Mapped[str] = mapped_column(String(500), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(100), default="")
    telegram_daily_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_daily_time: Mapped[str] = mapped_column(String(5), default="")  # "HH:MM" локального времени сервера

    team_members: Mapped[list["TeamMember"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    boards: Mapped[list["ConfigBoard"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    components: Mapped[list["ConfigComponent"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    status_priorities: Mapped[list["StatusPriority"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    role_hours_fields: Mapped[list["RoleHoursField"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    roles: Mapped[list["Role"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    role_status_buckets: Mapped[list["RoleStatusBucket"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    role_status_default_hours: Mapped[list["RoleStatusDefaultHours"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    pseudo_tasks: Mapped[list["PseudoTask"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    terminal_statuses: Mapped[list["TerminalStatus"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    directions: Mapped[list["ConfigDirection"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    vacations: Mapped[list["EmployeeVacation"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    epic_dependencies: Mapped[list["EpicTaskDependency"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    epic_snapshots: Mapped[list["EpicForecastSnapshot"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    root_tasks: Mapped[list["EmployeeRootTask"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )


# -------------------- Team --------------------

class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("config_id", "person_id", "role",
                         name="uq_team_config_person_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    person_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=True,
    )
    jira_account_id: Mapped[str] = mapped_column(String(100))
    jira_name: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str] = mapped_column(String(50), default="analyst")
    salary: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    config: Mapped[Config] = relationship(back_populates="team_members")
    person: Mapped[Person | None] = relationship()
    pseudo_tasks: Mapped[list["PseudoTask"]] = relationship(
        cascade="all, delete-orphan", back_populates="member"
    )


class ConfigBoard(Base):
    __tablename__ = "config_boards"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_board_id", name="uq_board_config_jiraid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    jira_board_id: Mapped[int] = mapped_column(Integer)

    config: Mapped[Config] = relationship(back_populates="boards")


class ConfigComponent(Base):
    __tablename__ = "config_components"
    __table_args__ = (
        UniqueConstraint("config_id", "name", name="uq_component_config_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))

    config: Mapped[Config] = relationship(back_populates="components")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("config_id", "name", name="uq_role_config_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    config: Mapped[Config] = relationship(back_populates="roles")


class RoleStatusBucket(Base):
    __tablename__ = "role_status_buckets"
    __table_args__ = (
        UniqueConstraint("config_id", "role", "jira_status",
                         name="uq_rsb_config_role_status"),
        Index("ix_rsb_config_role", "config_id", "role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    jira_status: Mapped[str] = mapped_column(String(100))
    bucket: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="role_status_buckets")


class RoleStatusDefaultHours(Base):
    __tablename__ = "role_status_default_hours"
    __table_args__ = (
        UniqueConstraint("config_id", "role", "jira_status",
                         name="uq_rsdh_config_role_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    jira_status: Mapped[str] = mapped_column(String(100))
    hours: Mapped[float] = mapped_column(Float)

    config: Mapped[Config] = relationship(back_populates="role_status_default_hours")


class StatusPriority(Base):
    __tablename__ = "status_priorities"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_status", name="uq_statusprio_config_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_status: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer)

    config: Mapped[Config] = relationship(back_populates="status_priorities")


class RoleHoursField(Base):
    __tablename__ = "role_hours_fields"
    __table_args__ = (
        UniqueConstraint("config_id", "role", name="uq_rolehours_config_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    customfield_id: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="role_hours_fields")


class PseudoTask(Base):
    __tablename__ = "pseudo_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    bucket: Mapped[str] = mapped_column(String(50))
    hours: Mapped[float] = mapped_column(Float)
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    target_sprint_num: Mapped[int | None] = mapped_column(Integer, nullable=True)

    config: Mapped[Config] = relationship(back_populates="pseudo_tasks")
    member: Mapped[TeamMember] = relationship(back_populates="pseudo_tasks")


class ConfigDirection(Base):
    """Направление — группа задач с общим pipeline работ (аналитика → разработка → тест)."""

    __tablename__ = "config_directions"
    __table_args__ = (
        UniqueConstraint("config_id", "name", name="uq_direction_config_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    labels: Mapped[list] = mapped_column(JSON)       # список Jira-меток, например ["Backend"]
    work_types: Mapped[list] = mapped_column(JSON)   # упорядоченный список: ["analytics","development","testing"]
    # work_type -> имя роли; пусто/нет ключа = системный дефолт (см. _WORK_TYPE_INFO)
    role_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    designer_id:  Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)

    config: Mapped["Config"] = relationship(back_populates="directions")


class TerminalStatus(Base):
    __tablename__ = "terminal_statuses"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_status", name="uq_termstatus_config_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_status: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    config: Mapped[Config] = relationship(back_populates="terminal_statuses")


class EmployeeVacation(Base):
    """Отпуск сотрудника — уровень конфига, применяется ко всем спринтам."""

    __tablename__ = "employee_vacations"
    __table_args__ = (
        Index("ix_emp_vac_config_owner", "config_id", "jira_account_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_account_id: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str] = mapped_column(String(10))  # "YYYY-MM-DD"
    end_date: Mapped[str] = mapped_column(String(10))    # "YYYY-MM-DD"

    config: Mapped["Config"] = relationship(back_populates="vacations")


class EpicTaskDependency(Base):
    """FS-зависимость задач в рамках эпика — уровень конфига, per epic key.

    from_bucket/to_bucket пусты — зависимость на уровне всей задачи (старое
    поведение); заданы — зависимость на конкретном этапе («колбаске») задачи.
    """

    __tablename__ = "epic_task_dependencies"
    __table_args__ = (
        UniqueConstraint("config_id", "epic_key", "from_key", "to_key",
                         "from_bucket", "to_bucket",
                         name="uq_epic_dep_unique"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    epic_key: Mapped[str] = mapped_column(String(50))
    from_key: Mapped[str] = mapped_column(String(50))
    to_key: Mapped[str] = mapped_column(String(50))
    from_bucket: Mapped[str] = mapped_column(String(50), default="")
    to_bucket: Mapped[str] = mapped_column(String(50), default="")

    config: Mapped["Config"] = relationship(back_populates="epic_dependencies")


class EmployeeRootTask(Base):
    """Стартовая (корневая) задача сотрудника — Start-Start якорь в очереди Ганта.

    epic_key — реальный ключ эпика/задачи Jira либо псевдо-ключ "sprint-N" для
    прогноза по утверждённому спринту (см. EpicTaskDependency).
    """

    __tablename__ = "employee_root_tasks"
    __table_args__ = (
        UniqueConstraint("config_id", "epic_key", "owner_id",
                         name="uq_root_task_owner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    epic_key: Mapped[str] = mapped_column(String(50))
    owner_id: Mapped[str] = mapped_column(String(100))
    task_key: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())

    config: Mapped["Config"] = relationship(back_populates="root_tasks")


class EpicForecastSnapshot(Base):
    """Снапшот прогноза эпика — один в день, перезаписывается при повторном построении."""

    __tablename__ = "epic_forecast_snapshots"
    __table_args__ = (
        UniqueConstraint("config_id", "epic_key", "captured_date",
                         name="uq_epic_snapshot_day"),
        Index("ix_epic_snapshot_config_epic", "config_id", "epic_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    epic_key: Mapped[str] = mapped_column(String(50))
    captured_date: Mapped[str] = mapped_column(String(10))   # "YYYY-MM-DD"
    start_date: Mapped[str] = mapped_column(String(10))
    hours_per_day: Mapped[float] = mapped_column(Float)
    completion_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    total_issues: Mapped[int] = mapped_column(Integer)
    done_issues: Mapped[int] = mapped_column(Integer)
    remaining_work_items: Mapped[int] = mapped_column(Integer)
    total_planned_hours: Mapped[float] = mapped_column(Float)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    config: Mapped["Config"] = relationship(back_populates="epic_snapshots")


# -------------------- Sprints --------------------

class Sprint(Base):
    __tablename__ = "sprints"
    __table_args__ = (
        Index("ix_sprints_status_num", "status", "sprint_num"),
        Index("ix_sprints_config", "config_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sprint_num: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))

    config_id: Mapped[int | None] = mapped_column(
        ForeignKey("configs.id", ondelete="CASCADE"), nullable=True,
    )

    config_snapshot: Mapped[dict] = mapped_column(JSON)
    owner_stats_snapshot: Mapped[list[dict]] = mapped_column(JSON)
    max_sprint_in_jira: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                          nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                        nullable=True)
    jira_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                                nullable=True)

    # Фаза 2.10: задачи, которые появились в Jira-спринте ПОСЛЕ approve.
    intrusions: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # Фаза 2.12: FS-зависимости задач [{from_key, to_key}, ...]
    task_dependencies: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    tasks: Mapped[list["SprintTask"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="sprint",
        order_by="SprintTask.position",
    )
    gantt_snapshots: Mapped[list["SprintGanttSnapshot"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="sprint",
        order_by="SprintGanttSnapshot.captured_at",
    )


class SprintTask(Base):
    __tablename__ = "sprint_tasks"
    __table_args__ = (
        Index("ix_sprint_tasks_sprint_pos", "sprint_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sprint_id: Mapped[int] = mapped_column(ForeignKey("sprints.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    task_data: Mapped[dict] = mapped_column(JSON)
    closed_task_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    sprint: Mapped[Sprint] = relationship(back_populates="tasks")


class SprintGanttSnapshot(Base):
    """Статичный снимок Ганта — фиксирует план на момент сохранения.

    Привязан либо к спринту (sprint_id), либо к эпику прогноза (config_id + epic_key) —
    ровно один из двух контекстов заполнен. Единый механизм снимков для истории
    спринтов и для прогноза реализации.
    """

    __tablename__ = "sprint_gantt_snapshots"
    __table_args__ = (
        Index("ix_sprint_gantt_snapshots_sprint", "sprint_id"),
        Index("ix_sprint_gantt_snapshots_epic", "config_id", "epic_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sprint_id: Mapped[int | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="CASCADE"), nullable=True,
    )
    config_id: Mapped[int | None] = mapped_column(
        ForeignKey("configs.id", ondelete="CASCADE"), nullable=True,
    )
    epic_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   server_default=func.now())
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gantt_start: Mapped[str] = mapped_column(String(10))   # "YYYY-MM-DD"
    hours_per_day: Mapped[float] = mapped_column(Float)
    gantt_items: Mapped[list[dict]] = mapped_column(JSON)

    sprint: Mapped[Sprint | None] = relationship(back_populates="gantt_snapshots")
