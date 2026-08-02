"""Application composition root."""

import logging

from freelance_agents.config import Settings, load_settings
from freelance_agents.core.company import Company
from freelance_agents.core.events.bus import EventBus
from freelance_agents.database import Database, SqlAlchemyWorkflowTransactionManager
from freelance_agents.logging_config import configure_logging
from freelance_agents.services import OrderIntakeService

logger = logging.getLogger(__name__)


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
            await self.database.close()
            logger.info("Database closed.")
        logger.info("%s stopped successfully.", self.company.name)
