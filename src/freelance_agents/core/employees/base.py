"""Base employee model."""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class EmployeeStatus(StrEnum):
    """Possible employee availability states."""

    OFFLINE = "offline"
    AVAILABLE = "available"
    BUSY = "busy"


@dataclass(slots=True)
class Employee:
    """Represent an employee participating in company work."""

    name: str
    role: str
    id: UUID = field(default_factory=uuid4)
    status: EmployeeStatus = EmployeeStatus.OFFLINE

    async def start(self) -> None:
        """Mark the employee as available."""
        self.status = EmployeeStatus.AVAILABLE

    async def stop(self) -> None:
        """Mark the employee as offline."""
        self.status = EmployeeStatus.OFFLINE
