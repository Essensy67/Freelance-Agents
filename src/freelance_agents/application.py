"""Application composition root."""

from freelance_agents.core.company import Company
from freelance_agents.core.events.bus import EventBus


class Application:
    """Compose and manage the application dependencies."""

    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.company = Company(name="Freelance Agents", event_bus=self.event_bus)

    async def run(self) -> None:
        """Start the company and report that the application is running."""
        await self.company.start()
        print(f"{self.company.name} started successfully.")

    async def shutdown(self) -> None:
        """Stop the company and its employees."""
        await self.company.stop()
