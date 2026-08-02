import asyncio
import logging
import signal
from collections.abc import Callable

import pytest

from freelance_agents.__main__ import run_application
from freelance_agents.application import Application
from freelance_agents.config import LogLevel, Settings
from freelance_agents.core.events import Event
from freelance_agents.logging_config import configure_logging


class BlockingCompany:
    """Test company that remains in startup until its task is cancelled."""

    def __init__(self) -> None:
        self.name = "Blocking Company"
        self.is_running = False
        self.started = asyncio.Event()
        self.stopped = False

    async def start(self) -> None:
        """Enter the running state and wait indefinitely."""
        self.is_running = True
        self.started.set()
        await asyncio.Event().wait()

    async def stop(self) -> None:
        """Record orderly shutdown."""
        self.is_running = False
        self.stopped = True


class SignalLoop:
    """Minimal signal-loop double for lifecycle tests."""

    def __init__(self) -> None:
        self.handlers: dict[signal.Signals, Callable[[], None]] = {}
        self.removed: list[signal.Signals] = []

    def add_signal_handler(
        self,
        process_signal: signal.Signals,
        callback: Callable[[signal.Signals], None],
        callback_signal: signal.Signals,
    ) -> None:
        """Capture a signal callback with its bound argument."""
        self.handlers[process_signal] = lambda: callback(callback_signal)

    def remove_signal_handler(self, process_signal: signal.Signals) -> bool:
        """Record signal-handler cleanup."""
        self.removed.append(process_signal)
        return self.handlers.pop(process_signal, None) is not None


def make_settings(**overrides: object) -> Settings:
    """Create settings isolated from local dotenv files."""
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        **overrides,
    )


async def test_application_logs_start_and_always_stops(
    caplog: pytest.LogCaptureFixture,
) -> None:
    telegram_secret = "telegram-log-secret"
    api_secret = "api-log-secret"
    settings = make_settings(
        telegram_bot_token=telegram_secret,
        ai_api_key=api_secret,
        log_level=LogLevel.INFO,
    )
    application = Application(settings=settings)
    events: list[Event] = []

    async def capture(event: Event) -> None:
        events.append(event)

    application.event_bus.subscribe("company.started", capture)
    application.event_bus.subscribe("company.stopped", capture)

    await application.run()

    assert [event.name for event in events] == [
        "company.started",
        "company.stopped",
    ]
    assert application.company.is_running is False
    assert application.database.is_initialized is False
    assert "Starting application with settings" in caplog.text
    assert "started successfully" in caplog.text
    assert "stopped successfully" in caplog.text
    assert "'telegram_bot_token_configured': True" in caplog.text
    assert "'ai_api_key_configured': True" in caplog.text
    assert telegram_secret not in caplog.text
    assert api_secret not in caplog.text


async def test_application_stops_and_propagates_startup_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "startup-error-secret"
    application = Application(settings=make_settings(ai_api_key=secret))

    async def fail_startup(event: Event) -> None:
        raise RuntimeError(f"{event.name}: {secret}")

    application.event_bus.subscribe("company.started", fail_startup)

    with pytest.raises(RuntimeError, match="company.started"):
        await application.run()

    assert application.company.is_running is False
    assert "Application startup failed" in caplog.text
    assert "stopped successfully" in caplog.text
    assert secret not in caplog.text


async def test_application_propagates_and_logs_shutdown_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = Application(settings=make_settings())

    async def fail_shutdown(event: Event) -> None:
        raise RuntimeError(f"Failed to handle {event.name}")

    application.event_bus.subscribe("company.stopped", fail_shutdown)

    with pytest.raises(RuntimeError, match="company.stopped"):
        await application.run()

    assert "Application shutdown failed" in caplog.text


async def test_application_shutdown_runs_when_cancelled() -> None:
    application = Application(settings=make_settings())
    company = BlockingCompany()
    application.company = company  # type: ignore[assignment]
    lifecycle_task = asyncio.create_task(application.run())
    await company.started.wait()

    lifecycle_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await lifecycle_task
    assert company.stopped is True


@pytest.mark.parametrize("process_signal", [signal.SIGINT, signal.SIGTERM])
async def test_process_signal_requests_shutdown(
    process_signal: signal.Signals,
) -> None:
    application = Application(settings=make_settings())
    company = BlockingCompany()
    application.company = company  # type: ignore[assignment]
    signal_loop = SignalLoop()
    lifecycle_task = asyncio.create_task(
        run_application(
            application,
            signal_loop=signal_loop,  # type: ignore[arg-type]
        )
    )
    await company.started.wait()

    signal_loop.handlers[process_signal]()
    await lifecycle_task

    assert company.stopped is True
    assert set(signal_loop.removed) == {signal.SIGINT, signal.SIGTERM}
    assert signal_loop.handlers == {}


def test_application_has_no_completion_provider_without_ai_settings() -> None:
    application = Application(settings=make_settings())

    assert application.completion_provider is None


def test_application_builds_and_closes_completion_provider_when_configured() -> None:
    application = Application(
        settings=make_settings(
            ai_api_key="ai-secret",
            ai_base_url="https://api.example.test",
            ai_model="gpt-test",
        )
    )

    assert application.completion_provider is not None


async def test_application_closes_completion_provider_on_shutdown() -> None:
    application = Application(
        settings=make_settings(
            ai_api_key="ai-secret",
            ai_base_url="https://api.example.test",
            ai_model="gpt-test",
        )
    )
    await application.database.initialize()

    await application.shutdown()

    assert application.completion_provider is not None


def test_logging_uses_configured_level() -> None:
    root_logger = logging.getLogger()
    original_level = root_logger.level
    try:
        configure_logging(LogLevel.ERROR)

        assert root_logger.level == logging.ERROR
    finally:
        root_logger.setLevel(original_level)
