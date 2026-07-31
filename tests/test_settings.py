from collections.abc import Iterator

import pytest
from pydantic import SecretStr, ValidationError

from freelance_agents.application import Application
from freelance_agents.config import (
    Environment,
    LogLevel,
    Settings,
    load_settings,
)

ENVIRONMENT_VARIABLES = (
    "FA_APP_NAME",
    "FA_ENVIRONMENT",
    "FA_DEBUG",
    "FA_LOG_LEVEL",
    "FA_DATABASE_URL",
    "FA_TELEGRAM_BOT_TOKEN",
    "FA_AI_API_KEY",
    "FA_AI_BASE_URL",
    "FA_AI_MODEL",
)


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove application variables so tests never use the host environment."""
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    yield


def test_settings_defaults() -> None:
    settings = load_settings(_env_file=None)

    assert settings.app_name == "Freelance Agents"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.debug is False
    assert settings.log_level is LogLevel.INFO
    assert settings.database_url == "sqlite+aiosqlite:///./data/freelance_agents.db"
    assert settings.telegram_bot_token is None
    assert settings.ai_api_key is None
    assert settings.ai_base_url is None
    assert settings.ai_model is None


def test_settings_accept_direct_arguments() -> None:
    settings = load_settings(
        _env_file=None,
        app_name="Direct Company",
        environment=Environment.TESTING,
        debug=True,
        log_level=LogLevel.WARNING,
        database_url="sqlite:///test.db",
        telegram_bot_token="telegram-secret",
        ai_api_key="ai-secret",
        ai_base_url="https://api.example.com/v1",
        ai_model="example-model",
    )

    assert settings.app_name == "Direct Company"
    assert settings.environment is Environment.TESTING
    assert settings.debug is True
    assert settings.log_level is LogLevel.WARNING
    assert settings.database_url == "sqlite:///test.db"
    assert settings.telegram_bot_token == SecretStr("telegram-secret")
    assert settings.ai_api_key == SecretStr("ai-secret")
    assert str(settings.ai_base_url) == "https://api.example.com/v1"
    assert settings.ai_model == "example-model"


def test_settings_read_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FA_APP_NAME", "Environment Company")
    monkeypatch.setenv("FA_ENVIRONMENT", "production")
    monkeypatch.setenv("FA_DEBUG", "true")
    monkeypatch.setenv("FA_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("FA_DATABASE_URL", "sqlite:///environment.db")
    monkeypatch.setenv("FA_AI_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("FA_AI_MODEL", "environment-model")

    settings = load_settings(_env_file=None)

    assert settings.app_name == "Environment Company"
    assert settings.environment is Environment.PRODUCTION
    assert settings.debug is True
    assert settings.log_level is LogLevel.ERROR
    assert settings.database_url == "sqlite:///environment.db"
    assert str(settings.ai_base_url) == "https://api.example.com/"
    assert settings.ai_model == "environment-model"


def test_environment_variable_names_are_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("fa_app_name", "Lowercase Company")

    assert load_settings(_env_file=None).app_name == "Lowercase Company"


@pytest.mark.parametrize(("raw_value", "expected"), [("true", True), ("false", False)])
def test_settings_convert_boolean_strings(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("FA_DEBUG", raw_value)

    assert load_settings(_env_file=None).debug is expected


def test_is_production() -> None:
    production = load_settings(_env_file=None, environment="production")
    development = load_settings(_env_file=None, environment="development")

    assert production.is_production is True
    assert development.is_production is False


def test_safe_summary_does_not_expose_secrets() -> None:
    telegram_secret = "telegram-super-secret"
    api_secret = "api-super-secret"
    settings = load_settings(
        _env_file=None,
        telegram_bot_token=telegram_secret,
        ai_api_key=api_secret,
        ai_base_url="https://api.example.com",
    )

    summary = settings.safe_summary()

    assert summary["telegram_bot_token_configured"] is True
    assert summary["ai_api_key_configured"] is True
    assert "telegram_bot_token" not in summary
    assert "ai_api_key" not in summary
    assert telegram_secret not in repr(summary)
    assert api_secret not in repr(summary)


def test_safe_summary_masks_database_password() -> None:
    password = "database-password"
    settings = load_settings(
        _env_file=None,
        database_url=f"postgresql+asyncpg://worker:{password}@db.example/app",
    )

    summary = settings.safe_summary()

    assert password not in repr(summary)
    assert summary["database_url"] == (
        "postgresql+asyncpg://worker:**********@db.example/app"
    )


def test_secret_str_masks_values_in_repr() -> None:
    secret = "never-show-this"
    settings = load_settings(_env_file=None, ai_api_key=secret)

    assert secret not in repr(settings)
    assert "**********" in repr(settings.ai_api_key)


def test_validation_errors_hide_secret_input() -> None:
    secret = "invalid-secret-input"

    with pytest.raises(ValidationError) as error:
        load_settings(_env_file=None, ai_api_key=[secret])

    assert secret not in str(error.value)
    assert secret not in repr(error.value)


def test_load_settings_returns_independent_instances() -> None:
    first = load_settings(_env_file=None)
    second = load_settings(_env_file=None)

    assert first is not second


def test_application_uses_injected_settings_and_app_name() -> None:
    settings = Settings(_env_file=None, app_name="Injected Company")

    application = Application(settings=settings)

    assert application.settings is settings
    assert application.company.name == "Injected Company"
