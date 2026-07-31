"""Command-line entry point for Freelance Agents."""

import asyncio
import logging
import signal
from collections.abc import Callable

from freelance_agents.application import Application

logger = logging.getLogger(__name__)


def _register_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    handler: Callable[[signal.Signals], None],
) -> tuple[signal.Signals, ...]:
    """Register supported process signals and return successful registrations."""
    registered: list[signal.Signals] = []
    for process_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(process_signal, handler, process_signal)
        except (NotImplementedError, RuntimeError):
            logger.debug("Signal handler unavailable for %s.", process_signal.name)
        else:
            registered.append(process_signal)
    return tuple(registered)


async def run_application(
    application: Application | None = None,
    *,
    signal_loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Run an application and translate process signals into cancellation."""
    active_application = application if application is not None else Application()
    loop = signal_loop if signal_loop is not None else asyncio.get_running_loop()
    lifecycle_task = asyncio.current_task()
    if lifecycle_task is None:
        raise RuntimeError("Application lifecycle requires an asyncio task")

    received_signal: signal.Signals | None = None

    def request_shutdown(process_signal: signal.Signals) -> None:
        nonlocal received_signal
        if received_signal is not None:
            return
        received_signal = process_signal
        logger.info("Received %s; requesting shutdown.", process_signal.name)
        lifecycle_task.cancel()

    registered_signals = _register_signal_handlers(loop, request_shutdown)
    try:
        await active_application.run()
    except asyncio.CancelledError:
        if received_signal is None:
            raise
    finally:
        for process_signal in registered_signals:
            loop.remove_signal_handler(process_signal)


def main() -> None:
    """Run the Freelance Agents application."""
    asyncio.run(run_application())


if __name__ == "__main__":
    main()
