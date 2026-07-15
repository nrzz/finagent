"""Runtime environment + settings store."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from finagent.config.schema import DEFAULT_SETTINGS, AppSettings


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", alias="FINAGENT_HOST")
    port: int = Field(default=8000, alias="FINAGENT_PORT")
    data_dir: Path = Field(default=Path("./data"), alias="FINAGENT_DATA_DIR")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/finagent.db",
        alias="FINAGENT_DATABASE_URL",
    )
    secret_key: str = Field(
        default="dev-insecure-fernet-key-replace=======", alias="FINAGENT_SECRET_KEY"
    )
    jwt_secret: str = Field(
        default="dev-insecure-jwt-secret-change-me", alias="FINAGENT_JWT_SECRET"
    )
    cors_origins: str = Field(default="*", alias="FINAGENT_CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="FINAGENT_LOG_LEVEL")


@lru_cache
def get_env() -> EnvSettings:
    return EnvSettings()


def ensure_data_dir() -> Path:
    env = get_env()
    env.data_dir.mkdir(parents=True, exist_ok=True)
    return env.data_dir


# In-memory settings cache; DB is source of truth after boot.
_settings: AppSettings = DEFAULT_SETTINGS.model_copy(deep=True)


def get_settings() -> AppSettings:
    return _settings


def set_settings(settings: AppSettings) -> AppSettings:
    global _settings
    _settings = settings
    return _settings


def load_yaml_overlay(path: Path) -> AppSettings | None:
    if not path.exists():
        return None
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppSettings.model_validate(raw)


def resolve_api_key(ref: str | None) -> str | None:
    """Resolve an API key from runtime secret cache or environment."""
    from finagent.security.store import get_secret

    return get_secret(ref)
