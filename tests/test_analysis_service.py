"""AnalysisService tests running entirely against in-memory fakes.

Neither this file nor ``AnalysisService`` imports ``freelance_agents.database``
or SQLAlchemy, matching the same "runs against fakes" proof used for
``OrderIntakeService`` in Issue #006.
"""

from uuid import uuid4

import pytest
from provider_fakes import FakeCompletionProvider
from workflow_fakes import FakeWorkflowTransactionManager, RecordingEventPublisher

from freelance_agents.core.analysis.errors import (
    AnalysisResponseError,
    AnalysisValidationError,
)
from freelance_agents.core.providers.errors import ProviderRateLimitError
from freelance_agents.core.providers.types import CompletionResponse, CompletionUsage
from freelance_agents.core.workflow.errors import (
    PlanAlreadyExistsError,
    PlanValidationError,
    ProjectNotFoundError,
)
from freelance_agents.core.workflow.statuses import MessageRole
from freelance_agents.core.workflow.value_objects import TaskInput
from freelance_agents.services.analysis import AnalysisService
from freelance_agents.services.dto import OrderIntakeCommand, PlanCommand
from freelance_agents.services.order_intake import OrderIntakeService

VALID_PLAN_JSON = '[{"title": "Design"}, {"title": "Build", "depends_on": [0]}]'


def make_response(content: str) -> CompletionResponse:
    return CompletionResponse(
        model="gpt-test",
        content=content,
        usage=CompletionUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )


@pytest.fixture
def harness():
    """Wire an ``OrderIntakeService`` and ``AnalysisService`` to shared fakes."""
    transactions = FakeWorkflowTransactionManager()
    events = RecordingEventPublisher()
    order_intake = OrderIntakeService(transactions=transactions, events=events)
    return transactions, events, order_intake


def make_analysis(harness, provider: FakeCompletionProvider) -> AnalysisService:
    transactions, _events, order_intake = harness
    return AnalysisService(
        transactions=transactions,
        order_intake=order_intake,
        provider=provider,
        model="gpt-test",
    )


async def test_analyze_order_creates_ordered_plan_and_persists_audit_messages(
    harness,
) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(response=make_response(VALID_PLAN_JSON))
    analysis = make_analysis(harness, provider)

    result = await analysis.analyze_order(intake.project_id)

    assert [task.title for task in result.tasks] == ["Design", "Build"]
    assert result.tasks[1].depends_on == (result.tasks[0].id,)
    assert len(provider.requests) == 1

    messages = transactions.committed.messages
    assert [message.role for message in messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.AGENT,
    ]
    assert messages[-1].content == VALID_PLAN_JSON
    assert all(
        message.conversation_id == intake.conversation_id for message in messages
    )

    assert [event.name for event in events.events][-1] == "plan.created"


async def test_analyze_order_rejects_unknown_project(harness) -> None:
    provider = FakeCompletionProvider(response=make_response(VALID_PLAN_JSON))
    analysis = make_analysis(harness, provider)

    with pytest.raises(ProjectNotFoundError):
        await analysis.analyze_order(uuid4())

    assert provider.requests == []


async def test_analyze_order_rejects_project_without_a_plan_twice(harness) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(response=make_response(VALID_PLAN_JSON))
    analysis = make_analysis(harness, provider)
    await analysis.analyze_order(intake.project_id)

    with pytest.raises(PlanAlreadyExistsError):
        await analysis.analyze_order(intake.project_id)

    assert len(provider.requests) == 1


async def test_analyze_order_never_calls_provider_when_plan_already_exists(
    harness,
) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    await order_intake.create_plan(
        intake.project_id, PlanCommand(tasks=(TaskInput(title="Manual task"),))
    )
    provider = FakeCompletionProvider(response=make_response(VALID_PLAN_JSON))
    analysis = make_analysis(harness, provider)

    with pytest.raises(PlanAlreadyExistsError):
        await analysis.analyze_order(intake.project_id)

    assert provider.requests == []


async def test_analyze_order_propagates_provider_error_without_persisting_anything(
    harness,
) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(error=ProviderRateLimitError("rate limited"))
    analysis = make_analysis(harness, provider)

    with pytest.raises(ProviderRateLimitError):
        await analysis.analyze_order(intake.project_id)

    assert transactions.committed.messages == []
    assert transactions.committed.tasks == {}


async def test_analyze_order_rejects_malformed_response_but_persists_audit_trail(
    harness,
) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(response=make_response("not valid json"))
    analysis = make_analysis(harness, provider)

    with pytest.raises(AnalysisResponseError):
        await analysis.analyze_order(intake.project_id)

    assert transactions.committed.tasks == {}
    messages = transactions.committed.messages
    assert [message.role for message in messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.AGENT,
    ]
    assert messages[-1].content == "not valid json"


async def test_analyze_order_rejects_invalid_plan_content_but_persists_audit_trail(
    harness,
) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(response=make_response('[{"title": "   "}]'))
    analysis = make_analysis(harness, provider)

    with pytest.raises(PlanValidationError):
        await analysis.analyze_order(intake.project_id)

    assert transactions.committed.tasks == {}
    assert len(transactions.committed.messages) == 3


async def test_analyze_order_rejects_oversized_order_before_calling_provider(
    harness,
) -> None:
    transactions, events, order_intake = harness
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="x" * 6001)
    )
    provider = FakeCompletionProvider(response=make_response(VALID_PLAN_JSON))
    analysis = make_analysis(harness, provider)

    with pytest.raises(AnalysisValidationError):
        await analysis.analyze_order(intake.project_id)

    assert provider.requests == []
