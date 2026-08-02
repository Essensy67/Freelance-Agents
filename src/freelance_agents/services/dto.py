"""Transport-neutral commands and results for the order-intake service.

Interface adapters (Telegram, web, CLI) construct these commands and read
these results; they never construct ORM models or import ``database``.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from freelance_agents.core.workflow.records import TaskRecord
from freelance_agents.core.workflow.statuses import (
    OrderIntakeStatus,
    ProjectWorkflowStatus,
)
from freelance_agents.core.workflow.value_objects import TaskInput


@dataclass(frozen=True, slots=True)
class OrderIntakeCommand:
    """Raw, transport-neutral order-intake input."""

    title: str
    description: str
    budget: Decimal | None = None
    request_key: str | None = None


@dataclass(frozen=True, slots=True)
class OrderIntakeResult:
    """Stable identifiers, statuses, and timestamps for an accepted order."""

    order_id: UUID
    project_id: UUID
    conversation_id: UUID
    order_status: OrderIntakeStatus
    project_status: ProjectWorkflowStatus
    created: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlanCommand:
    """A candidate ordered task plan for one project."""

    tasks: tuple[TaskInput, ...]


@dataclass(frozen=True, slots=True)
class PlanResult:
    """Persisted, ordered tasks created for one project."""

    project_id: UUID
    tasks: tuple[TaskRecord, ...]


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    """A read-only view of a project's order status and current tasks."""

    project_id: UUID
    order_id: UUID | None
    order_status: OrderIntakeStatus | None
    project_status: ProjectWorkflowStatus
    tasks: tuple[TaskRecord, ...]
