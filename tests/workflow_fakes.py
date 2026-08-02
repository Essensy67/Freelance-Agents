"""In-memory fakes satisfying the order-intake service ports.

These fakes implement ``services.ports`` structurally (via duck typing)
without importing SQLAlchemy or any other infrastructure module, proving
that ``OrderIntakeService`` only depends on ``core`` and ``services``.
"""

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from freelance_agents.core.events.models import Event
from freelance_agents.core.workflow.errors import IdempotencyConflictError
from freelance_agents.core.workflow.records import (
    ConversationRecord,
    MessageRecord,
    OrderRecord,
    ProjectRecord,
    TaskRecord,
)
from freelance_agents.core.workflow.statuses import (
    MessageRole,
    OrderIntakeStatus,
    ProjectWorkflowStatus,
    TaskStatus,
)
from freelance_agents.core.workflow.value_objects import OrderDetails, TaskDraft
from freelance_agents.services.ports import WorkflowUnitOfWork


@dataclass
class FakeWorkflowStore:
    """In-memory state committed across transactions."""

    orders: dict[UUID, OrderRecord] = field(default_factory=dict)
    projects: dict[UUID, ProjectRecord] = field(default_factory=dict)
    conversations: dict[UUID, ConversationRecord] = field(default_factory=dict)
    tasks: dict[UUID, TaskRecord] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)
    messages: list[MessageRecord] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


class _FakeOrders:
    def __init__(self, store: FakeWorkflowStore) -> None:
        self._store = store

    async def create(
        self, details: OrderDetails, request_key: str | None
    ) -> OrderRecord:
        if request_key is not None and any(
            order.client_request_key == request_key
            for order in self._store.orders.values()
        ):
            raise IdempotencyConflictError(f"Request key {request_key!r} already used")
        timestamp = _now()
        record = OrderRecord(
            id=uuid4(),
            title=details.title,
            description=details.description,
            status=OrderIntakeStatus.OPEN,
            budget=details.budget,
            client_request_key=request_key,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._store.orders[record.id] = record
        return record

    async def get(self, order_id: UUID) -> OrderRecord | None:
        return self._store.orders.get(order_id)

    async def find_by_request_key(self, request_key: str) -> OrderRecord | None:
        for order in self._store.orders.values():
            if order.client_request_key == request_key:
                return order
        return None


class _FakeProjects:
    def __init__(self, store: FakeWorkflowStore) -> None:
        self._store = store

    async def create(
        self, order_id: UUID, name: str, description: str
    ) -> ProjectRecord:
        timestamp = _now()
        record = ProjectRecord(
            id=uuid4(),
            order_id=order_id,
            name=name,
            description=description,
            status=ProjectWorkflowStatus.PLANNED,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._store.projects[record.id] = record
        return record

    async def get(self, project_id: UUID) -> ProjectRecord | None:
        return self._store.projects.get(project_id)

    async def find_by_order(self, order_id: UUID) -> ProjectRecord | None:
        for project in self._store.projects.values():
            if project.order_id == order_id:
                return project
        return None


class _FakeConversations:
    def __init__(self, store: FakeWorkflowStore) -> None:
        self._store = store

    async def create(self, project_id: UUID, title: str) -> ConversationRecord:
        timestamp = _now()
        record = ConversationRecord(
            id=uuid4(),
            project_id=project_id,
            title=title,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._store.conversations[record.id] = record
        return record

    async def find_open_for_project(
        self, project_id: UUID
    ) -> ConversationRecord | None:
        for conversation in self._store.conversations.values():
            if conversation.project_id == project_id:
                return conversation
        return None


class _FakeEvents:
    def __init__(self, store: FakeWorkflowStore) -> None:
        self._store = store

    async def record_intake_event(
        self, project_id: UUID, order_id: UUID, conversation_id: UUID
    ) -> None:
        self._store.events.append(
            {
                "project_id": project_id,
                "order_id": order_id,
                "conversation_id": conversation_id,
            }
        )


class _FakeMessages:
    def __init__(self, store: FakeWorkflowStore) -> None:
        self._store = store

    async def append(
        self, conversation_id: UUID, role: MessageRole, content: str
    ) -> MessageRecord:
        timestamp = _now()
        record = MessageRecord(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._store.messages.append(record)
        return record


class _FakeTasks:
    def __init__(self, store: FakeWorkflowStore) -> None:
        self._store = store

    async def create_many(
        self, project_id: UUID, drafts: list[TaskDraft]
    ) -> list[TaskRecord]:
        created = []
        for draft in drafts:
            timestamp = _now()
            record = TaskRecord(
                id=draft.id,
                project_id=project_id,
                title=draft.title,
                description=draft.description,
                capability=draft.capability,
                position=draft.position,
                status=TaskStatus.RECEIVED,
                depends_on=draft.depends_on,
                assigned_agent_id=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
            self._store.tasks[record.id] = record
            created.append(record)
        return created

    async def list_for_project(self, project_id: UUID) -> list[TaskRecord]:
        return sorted(
            (
                task
                for task in self._store.tasks.values()
                if task.project_id == project_id
            ),
            key=lambda task: task.position,
        )

    async def get(self, task_id: UUID) -> TaskRecord | None:
        return self._store.tasks.get(task_id)

    async def update_status(self, task_id: UUID, status: TaskStatus) -> TaskRecord:
        current = self._store.tasks[task_id]
        updated = TaskRecord(
            id=current.id,
            project_id=current.project_id,
            title=current.title,
            description=current.description,
            capability=current.capability,
            position=current.position,
            status=status,
            depends_on=current.depends_on,
            assigned_agent_id=current.assigned_agent_id,
            created_at=current.created_at,
            updated_at=_now(),
        )
        self._store.tasks[task_id] = updated
        return updated


class FakeWorkflowTransactionManager:
    """Commit-or-discard in-memory transactions mirroring ``Database.session``."""

    def __init__(self) -> None:
        self.committed = FakeWorkflowStore()

    def begin(self) -> "_FakeTransaction":
        """Return an async context manager yielding one transaction's ports."""
        return _FakeTransaction(self)


class _FakeTransaction:
    def __init__(self, manager: FakeWorkflowTransactionManager) -> None:
        self._manager = manager
        self._staged: FakeWorkflowStore | None = None

    async def __aenter__(self) -> WorkflowUnitOfWork:
        self._staged = copy.deepcopy(self._manager.committed)
        return WorkflowUnitOfWork(
            orders=_FakeOrders(self._staged),
            projects=_FakeProjects(self._staged),
            conversations=_FakeConversations(self._staged),
            events=_FakeEvents(self._staged),
            tasks=_FakeTasks(self._staged),
            messages=_FakeMessages(self._staged),
        )

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            assert self._staged is not None
            self._manager.committed = self._staged


class RecordingEventPublisher:
    """Record every published event for assertions."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        """Append the event to the recorded list."""
        self.events.append(event)
