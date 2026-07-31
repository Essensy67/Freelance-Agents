"""Virtual company aggregate."""

from dataclasses import dataclass, field

from freelance_agents.core.employees.base import Employee
from freelance_agents.core.events.bus import EventBus
from freelance_agents.core.events.models import Event


@dataclass(slots=True)
class Company:
    """Coordinate employees and publish company lifecycle events."""

    name: str
    event_bus: EventBus
    employees: list[Employee] = field(default_factory=list)
    is_running: bool = field(default=False, init=False)

    def add_employee(self, employee: Employee) -> None:
        """Add an employee, rejecting duplicate identifiers."""
        if any(existing.id == employee.id for existing in self.employees):
            raise ValueError(f"Employee with id {employee.id} already exists")
        self.employees.append(employee)

    async def start(self) -> None:
        """Start every employee and publish the company start event."""
        if self.is_running:
            raise RuntimeError("Company is already running")

        for employee in self.employees:
            await employee.start()

        self.is_running = True
        await self.event_bus.publish(
            Event(name="company.started", payload={"company": self.name})
        )

    async def stop(self) -> None:
        """Stop every employee and publish the company stop event."""
        if not self.is_running:
            return

        for employee in self.employees:
            await employee.stop()

        await self.event_bus.publish(
            Event(name="company.stopped", payload={"company": self.name})
        )
        self.is_running = False
