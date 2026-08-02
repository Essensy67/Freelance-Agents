"""Order-intake service tests against the real SQLAlchemy/SQLite adapter.

Covers the Issue #006 acceptance criteria that require a real transaction
boundary: linked-record creation, idempotent retries, transactional
rollback, and state surviving database recreation.
"""

from pathlib import Path

import pytest

from freelance_agents.core.events.models import Event
from freelance_agents.core.workflow.errors import (
    IdempotencyConflictError,
    PlanValidationError,
)
from freelance_agents.core.workflow.statuses import TaskStatus
from freelance_agents.core.workflow.value_objects import TaskInput
from freelance_agents.database.manager import Database
from freelance_agents.database.repositories import (
    ConversationRepository,
    FreelanceOrderRepository,
    ProjectEventRepository,
    ProjectRepository,
    ProjectTaskRepository,
)
from freelance_agents.database.workflow import (
    SqlAlchemyProjectEventRepositoryPort,
    SqlAlchemyWorkflowTransactionManager,
)
from freelance_agents.services.dto import OrderIntakeCommand, PlanCommand
from freelance_agents.services.order_intake import OrderIntakeService


def sqlite_url(path: Path) -> str:
    """Return an async SQLite URL for a temporary path."""
    return f"sqlite+aiosqlite:///{path}"


class RecordingEventPublisher:
    """Record every published event for assertions."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        """Append the event to the recorded list."""
        self.events.append(event)


async def test_receive_order_persists_linked_records_in_one_transaction(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "intake.db"))
    await database.initialize()
    service = OrderIntakeService(
        transactions=SqlAlchemyWorkflowTransactionManager(database),
        events=RecordingEventPublisher(),
    )

    result = await service.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )

    async with database.session() as session:
        orders = await FreelanceOrderRepository(session).list()
        projects = await ProjectRepository(session).list()
        conversations = await ConversationRepository(session).list()
        events = await ProjectEventRepository(session).list()

    assert [order.id for order in orders] == [result.order_id]
    assert [project.id for project in projects] == [result.project_id]
    assert projects[0].order_id == result.order_id
    assert [conversation.id for conversation in conversations] == [
        result.conversation_id
    ]
    assert conversations[0].project_id == result.project_id
    assert len(events) == 1
    assert events[0].project_id == result.project_id
    assert events[0].payload["order_id"] == str(result.order_id)

    await database.close()


async def test_receive_order_idempotency_persists_across_retries(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "idempotent.db"))
    await database.initialize()
    service = OrderIntakeService(
        transactions=SqlAlchemyWorkflowTransactionManager(database),
        events=RecordingEventPublisher(),
    )
    command = OrderIntakeCommand(
        title="Build a shop", description="A small storefront", request_key="client-1"
    )

    first = await service.receive_order(command)
    second = await service.receive_order(command)

    assert second.order_id == first.order_id
    assert second.project_id == first.project_id
    assert second.conversation_id == first.conversation_id
    assert second.created is False

    async with database.session() as session:
        assert len(await FreelanceOrderRepository(session).list()) == 1
        assert len(await ProjectRepository(session).list()) == 1
        assert len(await ConversationRepository(session).list()) == 1

    with pytest.raises(IdempotencyConflictError):
        await service.receive_order(
            OrderIntakeCommand(
                title="Different scope",
                description="A small storefront",
                request_key="client-1",
            )
        )

    await database.close()


async def test_receive_order_transaction_rolls_back_on_event_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(sqlite_url(tmp_path / "rollback.db"))
    await database.initialize()
    service = OrderIntakeService(
        transactions=SqlAlchemyWorkflowTransactionManager(database),
        events=RecordingEventPublisher(),
    )

    async def failing_record_intake_event(
        self, *args: object, **kwargs: object
    ) -> None:
        raise RuntimeError("event persistence failed")

    monkeypatch.setattr(
        SqlAlchemyProjectEventRepositoryPort,
        "record_intake_event",
        failing_record_intake_event,
    )

    with pytest.raises(RuntimeError, match="event persistence failed"):
        await service.receive_order(
            OrderIntakeCommand(title="Build a shop", description="A small storefront")
        )

    async with database.session() as session:
        assert await FreelanceOrderRepository(session).list() == []
        assert await ProjectRepository(session).list() == []
        assert await ConversationRepository(session).list() == []
        assert await ProjectEventRepository(session).list() == []

    await database.close()


async def test_create_plan_persists_ordered_tasks_and_state_survives_recreation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "plan.db"
    database = Database(sqlite_url(path))
    await database.initialize()
    service = OrderIntakeService(
        transactions=SqlAlchemyWorkflowTransactionManager(database),
        events=RecordingEventPublisher(),
    )
    intake = await service.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    await service.create_plan(
        intake.project_id,
        PlanCommand(tasks=(TaskInput(title="Design"), TaskInput(title="Build"))),
    )
    await database.close()

    second_database = Database(sqlite_url(path))
    await second_database.initialize()
    async with second_database.session() as session:
        tasks = await ProjectTaskRepository(session).list_by_project(intake.project_id)

    assert [task.title for task in tasks] == ["Design", "Build"]
    assert [task.position for task in tasks] == [0, 1]
    assert all(task.status.value == TaskStatus.RECEIVED.value for task in tasks)

    await second_database.close()


async def test_create_plan_rejects_invalid_plan_against_real_database(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "invalid-plan.db"))
    await database.initialize()
    service = OrderIntakeService(
        transactions=SqlAlchemyWorkflowTransactionManager(database),
        events=RecordingEventPublisher(),
    )
    intake = await service.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )

    with pytest.raises(PlanValidationError, match="blank"):
        await service.create_plan(
            intake.project_id, PlanCommand(tasks=(TaskInput(title="   "),))
        )

    async with database.session() as session:
        assert (
            await ProjectTaskRepository(session).list_by_project(intake.project_id)
            == []
        )

    await database.close()
