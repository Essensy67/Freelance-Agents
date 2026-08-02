"""Transaction-facing ports the order-intake service depends on.

These protocols define the transaction boundary described in Issue #006:
a service depends only on narrow repository protocols and an event
publisher protocol, never on SQLAlchemy. Concrete adapters live in
``database`` and are assembled in ``Application``; tests may satisfy these
protocols with in-memory fakes.
"""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from freelance_agents.core.events.models import Event
from freelance_agents.core.workflow.records import (
    ConversationRecord,
    MessageRecord,
    OrderRecord,
    ProjectRecord,
    TaskRecord,
)
from freelance_agents.core.workflow.statuses import MessageRole, TaskStatus
from freelance_agents.core.workflow.value_objects import OrderDetails, TaskDraft


class OrderRepositoryPort(Protocol):
    """Persist and retrieve order records within one transaction."""

    async def create(
        self, details: OrderDetails, request_key: str | None
    ) -> OrderRecord:
        """Persist a new order and return its record."""

    async def get(self, order_id: UUID) -> OrderRecord | None:
        """Return an order by id, or ``None`` when it does not exist."""

    async def find_by_request_key(self, request_key: str) -> OrderRecord | None:
        """Return the order created with a given idempotency key, if any."""


class ProjectRepositoryPort(Protocol):
    """Persist and retrieve project records within one transaction."""

    async def create(
        self, order_id: UUID, name: str, description: str
    ) -> ProjectRecord:
        """Persist a new project for an order and return its record."""

    async def get(self, project_id: UUID) -> ProjectRecord | None:
        """Return a project by id, or ``None`` when it does not exist."""

    async def find_by_order(self, order_id: UUID) -> ProjectRecord | None:
        """Return the project created for an order, if any."""


class ConversationRepositoryPort(Protocol):
    """Persist and retrieve conversation records within one transaction."""

    async def create(self, project_id: UUID, title: str) -> ConversationRecord:
        """Persist a new open conversation for a project."""

    async def find_open_for_project(
        self, project_id: UUID
    ) -> ConversationRecord | None:
        """Return the open conversation for a project, if any."""


class ProjectEventRepositoryPort(Protocol):
    """Persist structured project history without leaking private content."""

    async def record_intake_event(
        self, project_id: UUID, order_id: UUID, conversation_id: UUID
    ) -> None:
        """Persist an intake event linking an order, project, and conversation."""


class MessageRepositoryPort(Protocol):
    """Append private conversation messages within one transaction."""

    async def append(
        self, conversation_id: UUID, role: MessageRole, content: str
    ) -> MessageRecord:
        """Persist one private message and return its record."""


class ProjectTaskRepositoryPort(Protocol):
    """Persist and retrieve project task records within one transaction."""

    async def create_many(
        self, project_id: UUID, drafts: Sequence[TaskDraft]
    ) -> list[TaskRecord]:
        """Persist a validated, ordered set of tasks for a project."""

    async def list_for_project(self, project_id: UUID) -> list[TaskRecord]:
        """List a project's tasks in deterministic position order."""

    async def get(self, task_id: UUID) -> TaskRecord | None:
        """Return a task by id, or ``None`` when it does not exist."""

    async def update_status(self, task_id: UUID, status: TaskStatus) -> TaskRecord:
        """Persist a task's new status and return its updated record."""


@dataclass(frozen=True, slots=True)
class WorkflowUnitOfWork:
    """Bundle the repository ports available within one transaction."""

    orders: OrderRepositoryPort
    projects: ProjectRepositoryPort
    conversations: ConversationRepositoryPort
    events: ProjectEventRepositoryPort
    tasks: ProjectTaskRepositoryPort
    messages: MessageRepositoryPort


class WorkflowTransactionManager(Protocol):
    """Open a transactional unit of work for the order-intake service."""

    def begin(self) -> AbstractAsyncContextManager[WorkflowUnitOfWork]:
        """Return an async context manager yielding one transaction's ports."""


class EventPublisherPort(Protocol):
    """Publish domain events after a transaction commits."""

    async def publish(self, event: Event) -> None:
        """Publish one event to current subscribers."""
