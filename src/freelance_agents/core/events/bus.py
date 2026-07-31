"""In-process asynchronous event bus."""

from collections import defaultdict
from collections.abc import Awaitable, Callable

from freelance_agents.core.events.models import Event

type EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Deliver named events to asynchronous subscribers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe an asynchronous handler to an event name."""
        self._handlers[event_name].append(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all current subscribers in registration order."""
        for handler in tuple(self._handlers.get(event.name, ())):
            await handler(event)
