"""Application composition root."""

import logging

from freelance_agents.config import Settings, load_settings
from freelance_agents.core.company import Company
from freelance_agents.core.events.bus import EventBus
from freelance_agents.logging_config import configure_logging

logger = logging.getLogger(__name__)


class Application:
    """Compose and manage the application dependencies."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else load_settings()
        self.event_bus = EventBus()
        self.company = Company(
            name=self.settings.app_name,
            event_bus=self.event_bus,
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
        """Stop the company and its employees."""
        logger.info("Shutting down %s.", self.company.name)
        try:
            await self.company.stop()
        except Exception:
            logger.error("Application shutdown failed.")
            raise
        logger.info("%s stopped successfully.", self.company.name)
