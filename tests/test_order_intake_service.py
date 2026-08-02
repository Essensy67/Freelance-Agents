"""Order-intake service tests running entirely against in-memory fakes.

None of these tests import ``freelance_agents.database`` or SQLAlchemy,
proving the service only depends on ``core`` and ``services`` (Issue #006
acceptance criterion 8).
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from workflow_fakes import FakeWorkflowTransactionManager, RecordingEventPublisher

from freelance_agents.core.workflow.errors import (
    IdempotencyConflictError,
    OrderValidationError,
    PlanAlreadyExistsError,
    PlanValidationError,
    ProjectNotFoundError,
    TaskNotFoundError,
    TaskTransitionError,
)
from freelance_agents.core.workflow.statuses import TaskStatus
from freelance_agents.core.workflow.value_objects import TaskInput
from freelance_agents.services.dto import OrderIntakeCommand, PlanCommand
from freelance_agents.services.order_intake import OrderIntakeService


@pytest.fixture
def service():
    """Return an ``OrderIntakeService`` wired to fresh in-memory fakes."""
    transactions = FakeWorkflowTransactionManager()
    events = RecordingEventPublisher()
    return (
        OrderIntakeService(transactions=transactions, events=events),
        transactions,
        events,
    )


async def test_receive_order_creates_linked_order_project_conversation_and_event(
    service,
) -> None:
    svc, transactions, events = service
    command = OrderIntakeCommand(
        title="Build a landing page", description="One page site"
    )

    result = await svc.receive_order(command)

    assert result.created is True
    store = transactions.committed
    assert set(store.orders) == {result.order_id}
    assert set(store.projects) == {result.project_id}
    assert set(store.conversations) == {result.conversation_id}
    assert store.projects[result.project_id].order_id == result.order_id
    assert store.conversations[result.conversation_id].project_id == result.project_id
    assert len(store.events) == 1
    assert store.events[0]["order_id"] == result.order_id
    assert [event.name for event in events.events] == [
        "order.received",
        "project.created",
    ]


async def test_receive_order_rejects_blank_title_and_description(service) -> None:
    svc, _, _ = service
    with pytest.raises(OrderValidationError):
        await svc.receive_order(OrderIntakeCommand(title="   ", description="details"))
    with pytest.raises(OrderValidationError):
        await svc.receive_order(OrderIntakeCommand(title="Title", description="   "))


async def test_receive_order_rejects_non_positive_budget(service) -> None:
    svc, _, _ = service
    with pytest.raises(OrderValidationError):
        await svc.receive_order(
            OrderIntakeCommand(
                title="Title", description="details", budget=Decimal("0")
            )
        )
    with pytest.raises(OrderValidationError):
        await svc.receive_order(
            OrderIntakeCommand(
                title="Title", description="details", budget=Decimal("-5")
            )
        )


async def test_receive_order_is_idempotent_for_matching_retry(service) -> None:
    svc, transactions, events = service
    command = OrderIntakeCommand(
        title="Build a landing page",
        description="One page site",
        request_key="req-1",
    )

    first = await svc.receive_order(command)
    second = await svc.receive_order(command)

    assert second == (
        first.__class__(
            order_id=first.order_id,
            project_id=first.project_id,
            conversation_id=first.conversation_id,
            order_status=first.order_status,
            project_status=first.project_status,
            created=False,
            created_at=first.created_at,
        )
    )
    assert len(transactions.committed.orders) == 1
    assert len(transactions.committed.projects) == 1
    assert len(transactions.committed.conversations) == 1
    assert [event.name for event in events.events] == [
        "order.received",
        "project.created",
    ]


async def test_receive_order_rejects_conflicting_reuse_of_request_key(service) -> None:
    svc, _, _ = service
    await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details", request_key="req-2")
    )

    with pytest.raises(IdempotencyConflictError):
        await svc.receive_order(
            OrderIntakeCommand(
                title="Different title", description="details", request_key="req-2"
            )
        )


async def test_create_plan_persists_deterministic_task_order(service) -> None:
    svc, _, events = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )

    plan = await svc.create_plan(
        intake.project_id,
        PlanCommand(
            tasks=(
                TaskInput(title="Design"),
                TaskInput(title="Build"),
                TaskInput(title="Ship"),
            )
        ),
    )

    assert [task.title for task in plan.tasks] == ["Design", "Build", "Ship"]
    assert [task.position for task in plan.tasks] == [0, 1, 2]
    assert all(task.status is TaskStatus.RECEIVED for task in plan.tasks)
    assert [event.name for event in events.events][-1] == "plan.created"


async def test_create_plan_rejects_blank_titles(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )

    with pytest.raises(PlanValidationError):
        await svc.create_plan(
            intake.project_id, PlanCommand(tasks=(TaskInput(title="   "),))
        )


async def test_create_plan_rejects_empty_plan(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )

    with pytest.raises(PlanValidationError):
        await svc.create_plan(intake.project_id, PlanCommand(tasks=()))


async def test_create_plan_rejects_duplicate_task_ids(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )
    shared_id = uuid4()

    with pytest.raises(PlanValidationError):
        await svc.create_plan(
            intake.project_id,
            PlanCommand(
                tasks=(
                    TaskInput(title="Design", id=shared_id),
                    TaskInput(title="Build", id=shared_id),
                )
            ),
        )


async def test_create_plan_rejects_invalid_dependency_reference(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )

    with pytest.raises(PlanValidationError):
        await svc.create_plan(
            intake.project_id,
            PlanCommand(tasks=(TaskInput(title="Design", depends_on=(uuid4(),)),)),
        )


async def test_create_plan_accepts_valid_intra_plan_dependency(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )
    design_id = uuid4()

    plan = await svc.create_plan(
        intake.project_id,
        PlanCommand(
            tasks=(
                TaskInput(title="Design", id=design_id),
                TaskInput(title="Build", depends_on=(design_id,)),
            )
        ),
    )

    assert plan.tasks[1].depends_on == (design_id,)


async def test_create_plan_rejects_replanning_an_already_planned_project(
    service,
) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )
    await svc.create_plan(
        intake.project_id, PlanCommand(tasks=(TaskInput(title="Design"),))
    )

    with pytest.raises(PlanAlreadyExistsError):
        await svc.create_plan(
            intake.project_id, PlanCommand(tasks=(TaskInput(title="Rework"),))
        )


async def test_create_plan_rejects_unknown_project(service) -> None:
    svc, _, _ = service
    with pytest.raises(ProjectNotFoundError):
        await svc.create_plan(uuid4(), PlanCommand(tasks=(TaskInput(title="Design"),)))


async def test_transition_task_allows_legal_moves_and_rejects_illegal_ones(
    service,
) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )
    plan = await svc.create_plan(
        intake.project_id, PlanCommand(tasks=(TaskInput(title="Design"),))
    )
    task_id = plan.tasks[0].id

    accepted = await svc.transition_task(task_id, TaskStatus.ACCEPTED)
    assert accepted.status is TaskStatus.ACCEPTED

    with pytest.raises(TaskTransitionError):
        await svc.transition_task(task_id, TaskStatus.COMPLETED)


async def test_transition_task_rejects_mutating_a_terminal_task(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )
    plan = await svc.create_plan(
        intake.project_id, PlanCommand(tasks=(TaskInput(title="Design"),))
    )
    task_id = plan.tasks[0].id
    await svc.transition_task(task_id, TaskStatus.CANCELLED)

    with pytest.raises(TaskTransitionError):
        await svc.transition_task(task_id, TaskStatus.ACCEPTED)


async def test_transition_task_rejects_unknown_task(service) -> None:
    svc, _, _ = service
    with pytest.raises(TaskNotFoundError):
        await svc.transition_task(uuid4(), TaskStatus.ACCEPTED)


async def test_get_project_workflow_returns_order_status_and_tasks(service) -> None:
    svc, _, _ = service
    intake = await svc.receive_order(
        OrderIntakeCommand(title="Title", description="details")
    )
    await svc.create_plan(
        intake.project_id, PlanCommand(tasks=(TaskInput(title="Design"),))
    )

    snapshot = await svc.get_project_workflow(intake.project_id)

    assert snapshot.project_id == intake.project_id
    assert snapshot.order_id == intake.order_id
    assert snapshot.order_status == intake.order_status
    assert len(snapshot.tasks) == 1


async def test_get_project_workflow_rejects_unknown_project(service) -> None:
    svc, _, _ = service
    with pytest.raises(ProjectNotFoundError):
        await svc.get_project_workflow(uuid4())


async def test_published_events_contain_only_ids_and_statuses(service) -> None:
    svc, _, events = service
    await svc.receive_order(
        OrderIntakeCommand(title="Confidential title", description="Private details")
    )

    allowed_keys = {"order_id", "project_id", "conversation_id", "status", "task_count"}
    for event in events.events:
        assert set(event.payload).issubset(allowed_keys)
        assert "Confidential title" not in str(event.payload)
        assert "Private details" not in str(event.payload)
