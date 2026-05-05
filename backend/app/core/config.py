"""Настройки приложения. Читаются из .env через pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Jira
    jira_base_url: str
    jira_email: str
    jira_api_token: str

    # Прокси (опционально — если работает напрямую через VPN, оставить пустым)
    http_proxy: str | None = None
    https_proxy: str | None = None
    requests_ca_bundle: str | None = None
    verify_ssl: bool = True

    # БД
    database_url: str = "postgresql+psycopg://sprint_app:sprint_local_dev@localhost:5432/sprint_builder"


settings = Settings()
