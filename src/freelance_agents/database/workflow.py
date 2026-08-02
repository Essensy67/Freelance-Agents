"""SQLAlchemy adapter for the order-intake service transaction boundary.

Maps between persistence models and the plain ``core.workflow`` records the
``services`` ports expect, so ``OrderIntakeService`` never sees an ORM
object. Assembled once in ``Application`` and otherwise unused outside this
module.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from freelance_agents.core.workflow.errors import IdempotencyConflictError
from freelance_agents.core.workflow.records import (
    ConversationRecord,
    OrderRecord,
    ProjectRecord,
    TaskRecord,
)
from freelance_agents.core.workflow.statuses import (
    OrderIntakeStatus,
    ProjectWorkflowStatus,
    TaskStatus,
)
from freelance_agents.core.workflow.value_objects import OrderDetails, TaskDraft
from freelance_agents.database.manager import Database
from freelance_agents.database.models import (
    ConversationModel,
    ConversationStatus,
    FreelanceOrderModel,
    OrderStatus,
    ProjectEventType,
    ProjectModel,
    ProjectStatus,
    ProjectTaskModel,
    ProjectTaskStatus,
)
from freelance_agents.database.repositories import (
    ConversationRepository,
    FreelanceOrderRepository,
    ProjectEventRepository,
    ProjectRepository,
    ProjectTaskRepository,
)
from freelance_agents.services.ports import WorkflowUnitOfWork

_TASK_STATUS_BY_VALUE = {status.value: status for status in ProjectTaskStatus}


def _order_record(model: FreelanceOrderModel) -> OrderRecord:
    return OrderRecord(
        id=model.id,
        title=model.title,
        description=model.description,
        status=OrderIntakeStatus(model.status.value),
        budget=model.budget,
        client_request_key=model.client_request_key,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _project_record(model: ProjectModel) -> ProjectRecord:
    return ProjectRecord(
        id=model.id,
        order_id=model.order_id,
        name=model.name,
        description=model.description,
        status=ProjectWorkflowStatus(model.status.value),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _conversation_record(model: ConversationModel) -> ConversationRecord:
    return ConversationRecord(
        id=model.id,
        project_id=model.project_id,
        title=model.title,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _task_record(model: ProjectTaskModel) -> TaskRecord:
    return TaskRecord(
        id=model.id,
        project_id=model.project_id,
        title=model.title,
        description=model.description,
        capability=model.capability,
        position=model.position,
        status=TaskStatus(model.status.value),
        depends_on=tuple(UUID(value) for value in model.depends_on),
        assigned_agent_id=model.assigned_agent_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyOrderRepositoryPort:
    """Adapt ``FreelanceOrderRepository`` to the order-intake order port."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = FreelanceOrderRepository(session)

    async def create(
        self, details: OrderDetails, request_key: str | None
    ) -> OrderRecord:
        """Persist a new order, translating a duplicate key into a domain error."""
        try:
            model = await self._repository.create(
                title=details.title,
                description=details.description,
                status=OrderStatus.OPEN,
                budget=details.budget,
                client_request_key=request_key,
            )
        except IntegrityError as error:
            raise IdempotencyConflictError(
                f"Request key {request_key!r} was already used"
            ) from error
        return _order_record(model)

    async def get(self, order_id: UUID) -> OrderRecord | None:
        """Return an order by id, or ``None`` when it does not exist."""
        model = await self._repository.get(order_id)
        return _order_record(model) if model is not None else None

    async def find_by_request_key(self, request_key: str) -> OrderRecord | None:
        """Return the order created with a given idempotency key, if any."""
        model = await self._repository.get_by_client_request_key(request_key)
        return _order_record(model) if model is not None else None


class SqlAlchemyProjectRepositoryPort:
    """Adapt ``ProjectRepository`` to the order-intake project port."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = ProjectRepository(session)

    async def create(
        self, order_id: UUID, name: str, description: str
    ) -> ProjectRecord:
        """Persist a new project for an order and return its record."""
        model = await self._repository.create(
            order_id=order_id,
            name=name,
            description=description,
            status=ProjectStatus.PLANNED,
        )
        return _project_record(model)

    async def get(self, project_id: UUID) -> ProjectRecord | None:
        """Return a project by id, or ``None`` when it does not exist."""
        model = await self._repository.get(project_id)
        return _project_record(model) if model is not None else None

    async def find_by_order(self, order_id: UUID) -> ProjectRecord | None:
        """Return the project created for an order, if any."""
        model = await self._repository.get_by_order_id(order_id)
        return _project_record(model) if model is not None else None


class SqlAlchemyConversationRepositoryPort:
    """Adapt ``ConversationRepository`` to the order-intake conversation port."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = ConversationRepository(session)

    async def create(self, project_id: UUID, title: str) -> ConversationRecord:
        """Persist a new open conversation for a project."""
        model = await self._repository.create(
            project_id=project_id,
            title=title,
            status=ConversationStatus.OPEN,
        )
        return _conversation_record(model)

    async def find_open_for_project(
        self, project_id: UUID
    ) -> ConversationRecord | None:
        """Return the open conversation for a project, if any."""
        model = await self._repository.get_open_for_project(project_id)
        return _conversation_record(model) if model is not None else None


class SqlAlchemyProjectEventRepositoryPort:
    """Adapt ``ProjectEventRepository`` to the order-intake event port."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = ProjectEventRepository(session)

    async def record_intake_event(
        self, project_id: UUID, order_id: UUID, conversation_id: UUID
    ) -> None:
        """Persist an intake event linking an order, project, and conversation."""
        await self._repository.create(
            project_id=project_id,
            event_type=ProjectEventType.CREATED,
            payload={
                "order_id": str(order_id),
                "conversation_id": str(conversation_id),
            },
        )


class SqlAlchemyProjectTaskRepositoryPort:
    """Adapt ``ProjectTaskRepository`` to the order-intake task port."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = ProjectTaskRepository(session)

    async def create_many(
        self, project_id: UUID, drafts: Sequence[TaskDraft]
    ) -> list[TaskRecord]:
        """Persist a validated, ordered set of tasks for a project."""
        created = []
        for draft in drafts:
            model = await self._repository.create(
                id=draft.id,
                project_id=project_id,
                title=draft.title,
                description=draft.description,
                capability=draft.capability,
                position=draft.position,
                status=ProjectTaskStatus.RECEIVED,
                depends_on=[str(dependency_id) for dependency_id in draft.depends_on],
            )
            created.append(_task_record(model))
        return created

    async def list_for_project(self, project_id: UUID) -> list[TaskRecord]:
        """List a project's tasks in deterministic position order."""
        models = await self._repository.list_by_project(project_id)
        return [_task_record(model) for model in models]

    async def get(self, task_id: UUID) -> TaskRecord | None:
        """Return a task by id, or ``None`` when it does not exist."""
        model = await self._repository.get(task_id)
        return _task_record(model) if model is not None else None

    async def update_status(self, task_id: UUID, status: TaskStatus) -> TaskRecord:
        """Persist a task's new status and return its updated record."""
        model = await self._repository.update(
            task_id, status=_TASK_STATUS_BY_VALUE[status.value]
        )
        if model is None:
            raise LookupError(f"Task {task_id} does not exist")
        return _task_record(model)


class SqlAlchemyWorkflowTransactionManager:
    """Open a transactional unit of work backed by the async ``Database``."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[WorkflowUnitOfWork]:
        """Yield repository ports scoped to one committed-or-rolled-back session."""
        async with self._database.session() as session:
            yield WorkflowUnitOfWork(
                orders=SqlAlchemyOrderRepositoryPort(session),
                projects=SqlAlchemyProjectRepositoryPort(session),
                conversations=SqlAlchemyConversationRepositoryPort(session),
                events=SqlAlchemyProjectEventRepositoryPort(session),
                tasks=SqlAlchemyProjectTaskRepositoryPort(session),
            )
