from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""

    app_name: str = "messgo"
    environment: str = "dev"
    database_url: str = "sqlite:///./messgo.db"
    jwt_secret: str = "change-me-in-prod"
    access_token_ttl_minutes: int = 20
    refresh_token_ttl_days: int = 14
    bootstrap_invite_code: str = "START-MESSGO"
    invite_default_limit: int = 5
    invite_default_ttl_hours: int = 72
    cookie_secure: bool = False
    cookie_domain: str | None = None
    max_message_length: int = 2000
    max_group_size: int = 16

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def static_path(self) -> Path:
        return self.project_root / "app" / "static"

    @property
    def templates_path(self) -> Path:
        return self.project_root / "app" / "templates"


@lru_cache(1)
def get_settings() -> Settings:
    """Возвращает кэшированный объект настроек."""

    return Settings()
