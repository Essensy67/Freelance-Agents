"""Application composition root."""

import logging

from freelance_agents.config import Settings, load_settings
from freelance_agents.core.company import Company
from freelance_agents.core.events.bus import EventBus
from freelance_agents.core.providers import CompletionProvider, CostCalculator
from freelance_agents.database import (
    Database,
    RecordingCompletionProvider,
    SqlAlchemyWorkflowTransactionManager,
)
from freelance_agents.logging_config import configure_logging
from freelance_agents.providers import OpenAICompatibleProvider
from freelance_agents.services import OrderIntakeService

logger = logging.getLogger(__name__)


def _build_completion_provider(
    settings: Settings, database: Database
) -> CompletionProvider | None:
    """Construct the recording completion provider when AI settings are configured.

    Returns ``None`` when the API key, base URL, or model is unset, so the
    application can start without an AI provider configured (the current
    MVP does not require one; Issue #008 is the first consumer).
    """
    if settings.ai_api_key is None or settings.ai_base_url is None:
        return None
    if settings.ai_model is None:
        return None
    raw_provider = OpenAICompatibleProvider(
        base_url=str(settings.ai_base_url),
        api_key=settings.ai_api_key.get_secret_value(),
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )
    return RecordingCompletionProvider(
        raw_provider,
        database,
        CostCalculator(),
        provider_name="openai_compatible",
    )


class Application:
    """Compose and manage the application dependencies."""

    def __init__(
        self,
        settings: Settings | None = None,
        database: Database | None = None,
    ) -> None:
        self.settings = settings if settings is not None else load_settings()
        self.database = (
            database if database is not None else Database(self.settings.database_url)
        )
        self.event_bus = EventBus()
        self.company = Company(
            name=self.settings.app_name,
            event_bus=self.event_bus,
        )
        self.order_intake_service = OrderIntakeService(
            transactions=SqlAlchemyWorkflowTransactionManager(self.database),
            events=self.event_bus,
        )
        self.completion_provider = _build_completion_provider(
            self.settings, self.database
        )

    async def run(self) -> None:
        """Run startup and guarantee shutdown for this application instance."""
        configure_logging(self.settings.log_level)
        logger.info(
            "Starting application with settings: %s",
            self.settings.safe_summary(),
        )
        lifecycle_error: BaseException | None = None

        try:
            await self.database.initialize()
            if not await self.database.health_check():
                raise RuntimeError("Database health check failed")
            logger.info("Database initialized and healthy.")
            await self.company.start()
            logger.info("%s started successfully.", self.company.name)
        except BaseException as error:
            lifecycle_error = error
            if isinstance(error, Exception):
                logger.error("Application startup failed.")
            raise
        finally:
            try:
                await self.shutdown()
            except Exception:
                if lifecycle_error is None:
                    raise

    async def shutdown(self) -> None:
        """Stop the company and close persistence infrastructure."""
        logger.info("Shutting down %s.", self.company.name)
        try:
            await self.company.stop()
        except Exception:
            logger.error("Application shutdown failed.")
            raise
        finally:
            if self.completion_provider is not None:
                await self.completion_provider.aclose()
            await self.database.close()
            logger.info("Database closed.")
        logger.info("%s stopped successfully.", self.company.name)
