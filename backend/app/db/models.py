"""SQLAlchemy-модели нормализованного конфига.

Один конфиг (Config) = главная запись + 8 связанных таблиц.
Каскадное удаление: удаление конфига → улетают все child-таблицы.
"""

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


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
    status_buckets: Mapped[list["StatusBucket"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    status_priorities: Mapped[list["StatusPriority"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    bucket_hours_fields: Mapped[list["BucketHoursField"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    role_hours_fields: Mapped[list["RoleHoursField"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )
    strict_assignee_buckets: Mapped[list["StrictAssigneeBucket"]] = relationship(
        cascade="all, delete-orphan", back_populates="config"
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_account_id", name="uq_team_config_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_account_id: Mapped[str] = mapped_column(String(100))
    jira_name: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    config: Mapped[Config] = relationship(back_populates="team_members")


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


class StatusBucket(Base):
    """Маппинг: имя статуса в Jira → бакет ('Анализ' | 'Тестирование')."""
    __tablename__ = "status_buckets"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_status", name="uq_statusbucket_config_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_status: Mapped[str] = mapped_column(String(100))
    bucket: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="status_buckets")


class StatusPriority(Base):
    """Числовой приоритет статуса при наборе спринта (меньше = раньше)."""
    __tablename__ = "status_priorities"
    __table_args__ = (
        UniqueConstraint("config_id", "jira_status", name="uq_statusprio_config_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    jira_status: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer)

    config: Mapped[Config] = relationship(back_populates="status_priorities")


class BucketHoursField(Base):
    """Какое customfield использовать как оценку для бакета."""
    __tablename__ = "bucket_hours_fields"
    __table_args__ = (
        UniqueConstraint("config_id", "bucket", name="uq_buckethours_config_bucket"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    bucket: Mapped[str] = mapped_column(String(50))
    customfield_id: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="bucket_hours_fields")


class RoleHoursField(Base):
    """Поля часов по ролям — analyst/tester/developer."""
    __tablename__ = "role_hours_fields"
    __table_args__ = (
        UniqueConstraint("config_id", "role", name="uq_rolehours_config_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50))
    customfield_id: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="role_hours_fields")


class StrictAssigneeBucket(Base):
    """Бакеты, для которых assignee обязательно должен быть из team_members."""
    __tablename__ = "strict_assignee_buckets"
    __table_args__ = (
        UniqueConstraint("config_id", "bucket", name="uq_strict_config_bucket"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("configs.id", ondelete="CASCADE"))
    bucket: Mapped[str] = mapped_column(String(50))

    config: Mapped[Config] = relationship(back_populates="strict_assignee_buckets")
