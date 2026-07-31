"""Type-safe application settings loaded from the environment."""

from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported application runtime environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported application logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    """Validated infrastructure settings for an application instance."""

    model_config = SettingsConfigDict(
        env_prefix="FA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    app_name: str = "Freelance Agents"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    database_url: str = "sqlite+aiosqlite:///./data/freelance_agents.db"
    telegram_bot_token: SecretStr | None = None
    ai_api_key: SecretStr | None = None
    ai_base_url: AnyHttpUrl | None = None
    ai_model: str | None = None

    @property
    def is_production(self) -> bool:
        """Return whether the application runs in production."""
        return self.environment is Environment.PRODUCTION

    def safe_summary(self) -> dict[str, object]:
        """Return settings safe for diagnostics without secret values."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "debug": self.debug,
            "log_level": self.log_level,
            "database_url": _redact_url_password(self.database_url),
            "ai_base_url": str(self.ai_base_url) if self.ai_base_url else None,
            "ai_model": self.ai_model,
            "telegram_bot_token_configured": bool(
                self.telegram_bot_token and self.telegram_bot_token.get_secret_value()
            ),
            "ai_api_key_configured": bool(
                self.ai_api_key and self.ai_api_key.get_secret_value()
            ),
        }


def load_settings(**overrides: object) -> Settings:
    """Create a new settings instance with optional direct overrides."""
    return Settings(**overrides)


def _redact_url_password(url: str) -> str:
    """Mask a URL password while preserving non-secret connection details."""
    parsed = urlsplit(url)
    if parsed.password is None:
        return url
    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    netloc = f"{username}:**********@{hostname}{port}"
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )
