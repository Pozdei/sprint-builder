"""SQLAlchemy-модели.

Фаза 2: расширили модель данных под несколько ролей (analyst / designer /
designer_lead / developer / developer_lead).

Изменения относительно фазы 1:
- В team_members добавлена колонка role.
- Удалены status_buckets и strict_assignee_buckets (были глобальными).
- Добавлены: roles, role_status_buckets, role_status_default_hours, pseudo_tasks.
- В configs добавлены leader_hours и leader_management_enabled.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# -------------------- Config (главная) --------------------

class Config(Base):
    __tablename__ = "configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    project_key: Mapped[str] = mapped_column(String(50))
    sprint_field: Mapped[str] = mapped_column(String(50))
    responsible_field: Mapped[str] = mapped_column(String(50))
    hours_per_person: Mapped[float] = mapped_column(Float)
    default_task_hours: Mapped[float] = mapped_column(Float)

    # Новые поля для лидов
    leader_hours: Mapped[float] = mapped_column(Float, default=20.0)
    leader_management_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Дочерние таблицы
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
    # Новые
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


# -------------------- Team --------------------

class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_account_id", "role",
                         name="uq_team_config_account_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_account_id: Mapped[str] = mapped_column(String(100))
    jira_name: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Новое: роль человека (analyst / designer / designer_lead / developer / developer_lead)
    role: Mapped[str] = mapped_column(String(50), default="analyst")

    config: Mapped[Config] = relationship(back_populates="team_members")
    pseudo_tasks: Mapped[list["PseudoTask"]] = relationship(
        cascade="all, delete-orphan", back_populates="member"
    )


# -------------------- Доски и компоненты --------------------

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


# -------------------- Roles --------------------

class Role(Base):
    """Роль в конфиге: analyst, designer и т.п.

    Поле enabled управляет тем, формируется ли спринт для этой роли.
    is_lead — флаг лида (для авто-добавления псевдо-задачи 'Руководство').
    """
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("config_id", "name", name="uq_role_config_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))  # analyst / designer / ...
    display_name: Mapped[str] = mapped_column(String(100))  # "Аналитик", "Дизайнер"
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    config: Mapped[Config] = relationship(back_populates="roles")


# -------------------- Маппинг (роль, статус) → бакет --------------------

class RoleStatusBucket(Base):
    """Статус Jira → бакет, в разрезе роли.

    Один статус может быть в разных бакетах у разных ролей.
    Пример: 'В разработке' для разработчика = 'Разработка', для аналитика = 'Тестирование'.
    """
    __tablename__ = "role_status_buckets"
    __table_args__ = (
        UniqueConstraint("config_id", "role", "jira_status",
                         name="uq_rsb_config_role_status"),
        Index("ix_rsb_config_role", "config_id", "role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))  # ссылка на roles.name (мягкая)
    jira_status: Mapped[str] = mapped_column(String(100))
    bucket: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="role_status_buckets")


# -------------------- Дефолтные часы для пары (роль, статус) --------------------

class RoleStatusDefaultHours(Base):
    """Часы по умолчанию для конкретной пары (роль, статус).

    Применяется, когда у задачи нет оценки и она в указанном статусе у роли.
    Например, (developer_lead, 'Код-ревью') = 1 — лид тратит на ревью 1ч.
    Если записи нет — используется глобальный default_task_hours.
    """
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


# -------------------- Приоритеты статусов и поля часов --------------------

class StatusPriority(Base):
    """Приоритет статуса при наборе спринта. Сейчас один на статус — глобально."""
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
    """Поля часов по ролям — analyst/tester/developer.

    Используется в estimate_hours: для роли N → customfield_X.
    """
    __tablename__ = "role_hours_fields"
    __table_args__ = (
        UniqueConstraint("config_id", "role", name="uq_rolehours_config_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    customfield_id: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="role_hours_fields")


# -------------------- Псевдо-задачи (отпуск, обучение, руководство) --------------------

class PseudoTask(Base):
    """Псевдо-задача, не из Jira. Привязана к конкретному человеку.

    Логика попадания в спринт N:
      target_sprint_num == N → попадает (разовая на конкретный спринт)
      target_sprint_num is None и recurring → попадает (постоянная)
      иначе → не попадает
    """
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


class TerminalStatus(Base):
    """Терминальные статусы — те, при которых задача считается выполненной.

    Используется при закрытии спринта для подсчёта процента выполнения.
    """
    __tablename__ = "terminal_statuses"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_status", name="uq_termstatus_config_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_status: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    config: Mapped[Config] = relationship(back_populates="terminal_statuses")


# -------------------- История спринтов (без изменений) --------------------

class Sprint(Base):
    __tablename__ = "sprints"
    __table_args__ = (
        Index("ix_sprints_status_num", "status", "sprint_num"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sprint_num: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))  # 'draft' | 'approved' | 'closed'

    config_snapshot: Mapped[dict] = mapped_column(JSON)
    owner_stats_snapshot: Mapped[list[dict]] = mapped_column(JSON)
    max_sprint_in_jira: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                          nullable=True)
    # Поля закрытия (фаза 2.5)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                        nullable=True)
    # completeDate из Jira на момент закрытия
    jira_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                                nullable=True)

    tasks: Mapped[list["SprintTask"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="sprint",
        order_by="SprintTask.position",
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
    # Снапшот состояния задачи на момент закрытия спринта (фаза 2.5)
    closed_task_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    sprint: Mapped[Sprint] = relationship(back_populates="tasks")
