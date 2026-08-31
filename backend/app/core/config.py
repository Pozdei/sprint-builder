"""Настройки приложения. Читаются из .env через pydantic-settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRET = "change-me-in-production-please"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Jira
    jira_base_url: str
    jira_email: str
    jira_api_token: str

    # Telegram — один глобальный бот на всю систему; chat_id задаётся per-конфиг.
    telegram_bot_token: str = ""

    # AI-срез — глобальные фолбэк-ключи, если не заданы на конфиге.
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""

    # AI-срез — локальный/корпоративный OpenAI-совместимый эндпоинт (внутренняя
    # сеть, без ключа). Провайдер "local" не имеет per-конфиг настроек — только .env.
    ai_local_base_url: str = ""
    ai_local_api_key: str = ""
    ai_local_model: str = "Qwen3.8-27B-FP8"

    # Прокси
    http_proxy: str | None = None
    https_proxy: str | None = None
    requests_ca_bundle: str | None = None
    verify_ssl: bool = True

    # БД
    database_url: str = "postgresql+psycopg://sprint_app:sprint_local_dev@localhost:5432/sprint_builder"

    # Auth — обязательны для работы
    jwt_secret: str = _INSECURE_JWT_SECRET
    jwt_expire_hours: int = 24

    # Первый администратор — создаётся при первом старте из .env
    admin_email: str = "admin@local"
    admin_password: str = "change-me"

    @field_validator("jwt_secret")
    @classmethod
    def _reject_insecure_jwt_secret(cls, v: str) -> str:
        # jwt_secret — это и подпись JWT, и ключ Fernet-шифрования per-конфиг токенов
        # (см. core/security.py), поэтому дефолт или опечатка в имени env-переменной
        # (env_file_encoding + extra="ignore" её тихо проглотит) не должны проходить молча.
        if v == _INSECURE_JWT_SECRET or len(v) < 32:
            raise ValueError(
                "JWT_SECRET не задан, слишком короткий (<32 символов) или равен небезопасному "
                'значению по умолчанию. Сгенерируйте: python3 -c "import secrets; '
                'print(secrets.token_urlsafe(32))" и укажите как JWT_SECRET в .env.'
            )
        return v


settings = Settings()
