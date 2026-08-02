"""Order intake and task-workflow application service.

Implements the Issue #006 vertical slice: accept a client order, create its
project/conversation/intake event in one transaction, replace an unplanned
project's task list, inspect the current workflow, and transition individual
tasks through their lifecycle. This service depends only on the ports in
``services.ports`` and the domain types in ``core.workflow`` — never on
SQLAlchemy, Telegram, or an AI provider.
"""

import logging
from uuid import UUID

from freelance_agents.core.events.models import Event
from freelance_agents.core.workflow.errors import (
    IdempotencyConflictError,
    PlanAlreadyExistsError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from freelance_agents.core.workflow.records import OrderRecord, TaskRecord
from freelance_agents.core.workflow.statuses import (
    TaskStatus,
    ensure_valid_task_transition,
)
from freelance_agents.core.workflow.value_objects import OrderDetails, TaskPlan
from freelance_agents.services.dto import (
    OrderIntakeCommand,
    OrderIntakeResult,
    PlanCommand,
    PlanResult,
    WorkflowSnapshot,
)
from freelance_agents.services.ports import (
    EventPublisherPort,
    WorkflowTransactionManager,
    WorkflowUnitOfWork,
)

logger = logging.getLogger(__name__)


class OrderIntakeService:
    """Accept client orders and manage the resulting project task workflow."""

    def __init__(
        self,
        transactions: WorkflowTransactionManager,
        events: EventPublisherPort,
    ) -> None:
        self._transactions = transactions
        self._events = events

    async def receive_order(self, command: OrderIntakeCommand) -> OrderIntakeResult:
        """Create, or idempotently return, an order/project/conversation/event.

        A blank title, blank description, or non-positive budget raises
        ``OrderValidationError`` before any transaction opens. Repeating an
        equivalent command with the same ``request_key`` returns the
        original result; reuse with materially different content raises
        ``IdempotencyConflictError``.
        """
        details = OrderDetails.create(
            command.title, command.description, command.budget
        )

        async with self._transactions.begin() as uow:
            if command.request_key is not None:
                existing_order = await uow.orders.find_by_request_key(
                    command.request_key
                )
                if existing_order is not None:
                    return await self._existing_intake_result(
                        uow, existing_order, details, command.request_key
                    )

            order = await uow.orders.create(details, command.request_key)
            project = await uow.projects.create(
                order.id, details.title, details.description
            )
            conversation = await uow.conversations.create(
                project.id, f"{details.title} intake"
            )
            await uow.events.record_intake_event(project.id, order.id, conversation.id)

        result = OrderIntakeResult(
            order_id=order.id,
            project_id=project.id,
            conversation_id=conversation.id,
            order_status=order.status,
            project_status=project.status,
            created=True,
            created_at=order.created_at,
        )
        await self._publish(
            Event(
                name="order.received",
                payload={
                    "order_id": str(order.id),
                    "project_id": str(project.id),
                    "status": str(order.status),
                },
            )
        )
        await self._publish(
            Event(
                name="project.created",
                payload={
                    "project_id": str(project.id),
                    "order_id": str(order.id),
                    "status": str(project.status),
                },
            )
        )
        return result

    async def create_plan(self, project_id: UUID, plan: PlanCommand) -> PlanResult:
        """Persist a validated, ordered task plan for an unplanned project.

        Raises ``ProjectNotFoundError`` for an unknown project and
        ``PlanAlreadyExistsError`` when the project already has tasks;
        ``PlanValidationError`` (via ``TaskPlan.create``) rejects blank
        titles, duplicate task ids, and dangling dependency references.
        """
        async with self._transactions.begin() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project {project_id} does not exist")
            existing_tasks = await uow.tasks.list_for_project(project_id)
            if existing_tasks:
                raise PlanAlreadyExistsError(f"Project {project_id} already has a plan")

            task_plan = TaskPlan.create(project_id, plan.tasks)
            created_tasks = await uow.tasks.create_many(project_id, task_plan.tasks)

        result = PlanResult(project_id=project_id, tasks=tuple(created_tasks))
        await self._publish(
            Event(
                name="plan.created",
                payload={
                    "project_id": str(project_id),
                    "task_count": len(created_tasks),
                },
            )
        )
        return result

    async def get_project_workflow(self, project_id: UUID) -> WorkflowSnapshot:
        """Return the current order status, project status, and tasks."""
        async with self._transactions.begin() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project {project_id} does not exist")
            order = await uow.orders.get(project.order_id) if project.order_id else None
            tasks = await uow.tasks.list_for_project(project_id)

        return WorkflowSnapshot(
            project_id=project.id,
            order_id=project.order_id,
            order_status=order.status if order is not None else None,
            project_status=project.status,
            tasks=tuple(tasks),
        )

    async def transition_task(
        self, task_id: UUID, target_status: TaskStatus
    ) -> TaskRecord:
        """Transition a task to ``target_status``, enforcing legal lifecycle moves.

        Raises ``TaskNotFoundError`` for an unknown task and
        ``TaskTransitionError`` for a skipped state or a mutated terminal
        task.
        """
        async with self._transactions.begin() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                raise TaskNotFoundError(f"Task {task_id} does not exist")
            ensure_valid_task_transition(task.status, target_status)
            updated = await uow.tasks.update_status(task_id, target_status)

        return updated

    async def _existing_intake_result(
        self,
        uow: WorkflowUnitOfWork,
        existing_order: OrderRecord,
        details: OrderDetails,
        request_key: str,
    ) -> OrderIntakeResult:
        if (
            existing_order.title != details.title
            or existing_order.description != details.description
            or existing_order.budget != details.budget
        ):
            raise IdempotencyConflictError(
                f"Request key {request_key!r} was already used "
                "with different order content"
            )
        project = await uow.projects.find_by_order(existing_order.id)
        if project is None:
            raise ProjectNotFoundError(
                f"Order {existing_order.id} has no associated project"
            )
        conversation = await uow.conversations.find_open_for_project(project.id)
        if conversation is None:
            raise ProjectNotFoundError(f"Project {project.id} has no open conversation")
        return OrderIntakeResult(
            order_id=existing_order.id,
            project_id=project.id,
            conversation_id=conversation.id,
            order_status=existing_order.status,
            project_status=project.status,
            created=False,
            created_at=existing_order.created_at,
        )

    async def _publish(self, event: Event) -> None:
        try:
            await self._events.publish(event)
        except Exception:
            logger.error("Failed to publish event %s", event.name)
            raise
