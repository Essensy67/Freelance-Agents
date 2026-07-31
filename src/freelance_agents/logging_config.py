"""Standard-library logging configuration for the application."""

import logging

from freelance_agents.config import LogLevel

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(log_level: LogLevel) -> None:
    """Configure application logging at the requested level."""
    logging.basicConfig(level=log_level.value, format=LOG_FORMAT)
    logging.getLogger().setLevel(log_level.value)
