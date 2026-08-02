"""Read-model records returned by workflow repository ports.

These mirror persisted aggregates as plain, immutable data so services and
their tests never depend on ORM objects.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from freelance_agents.core.workflow.statuses import (
    MessageRole,
    OrderIntakeStatus,
    ProjectWorkflowStatus,
    TaskStatus,
)


@dataclass(frozen=True, slots=True)
class OrderRecord:
    """A persisted freelance order, without marketplace integration details."""

    id: UUID
    title: str
    description: str
    status: OrderIntakeStatus
    budget: Decimal | None
    client_request_key: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    """A persisted project and its optional source order."""

    id: UUID
    order_id: UUID | None
    name: str
    description: str
    status: ProjectWorkflowStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """A persisted project conversation."""

    id: UUID
    project_id: UUID | None
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """One persisted, private conversation message."""

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """One persisted, ordered unit of work belonging to a project."""

    id: UUID
    project_id: UUID
    title: str
    description: str
    capability: str | None
    position: int
    status: TaskStatus
    depends_on: tuple[UUID, ...]
    assigned_agent_id: UUID | None
    created_at: datetime
    updated_at: datetime
