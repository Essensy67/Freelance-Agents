from uuid import uuid4

import pytest

from freelance_agents.core.company import Company
from freelance_agents.core.employees import Employee, EmployeeStatus
from freelance_agents.core.events import Event, EventBus


async def test_company_starts_and_stops_employees_and_publishes_events() -> None:
    event_bus = EventBus()
    events: list[Event] = []

    async def capture(event: Event) -> None:
        events.append(event)

    event_bus.subscribe("company.started", capture)
    event_bus.subscribe("company.stopped", capture)
    company = Company(name="Test Company", event_bus=event_bus)
    employee = Employee(name="Alex", role="Developer")
    company.add_employee(employee)

    await company.start()

    assert company.is_running is True
    assert employee.status is EmployeeStatus.AVAILABLE
    assert [event.name for event in events] == ["company.started"]

    await company.stop()

    assert company.is_running is False
    assert employee.status is EmployeeStatus.OFFLINE
    assert [event.name for event in events] == [
        "company.started",
        "company.stopped",
    ]


async def test_company_rejects_repeated_start() -> None:
    company = Company(name="Test Company", event_bus=EventBus())
    await company.start()

    with pytest.raises(RuntimeError, match="already running"):
        await company.start()


def test_company_rejects_duplicate_employee_id() -> None:
    company = Company(name="Test Company", event_bus=EventBus())
    employee_id = uuid4()
    company.add_employee(Employee(name="Alex", role="Developer", id=employee_id))

    with pytest.raises(ValueError, match=str(employee_id)):
        company.add_employee(Employee(name="Sam", role="Designer", id=employee_id))
