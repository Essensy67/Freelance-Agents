"""AnalysisService tests against the real SQLAlchemy/SQLite adapter."""

from pathlib import Path

import pytest
from provider_fakes import FakeCompletionProvider

from freelance_agents.core.analysis.errors import AnalysisResponseError
from freelance_agents.core.events.models import Event
from freelance_agents.core.providers.errors import ProviderTimeoutError
from freelance_agents.core.providers.types import CompletionResponse, CompletionUsage
from freelance_agents.database.manager import Database
from freelance_agents.database.repositories import (
    ConversationRepository,
    MessageRepository,
    ProjectTaskRepository,
)
from freelance_agents.database.workflow import SqlAlchemyWorkflowTransactionManager
from freelance_agents.services.analysis import AnalysisService
from freelance_agents.services.dto import OrderIntakeCommand
from freelance_agents.services.order_intake import OrderIntakeService


def sqlite_url(path: Path) -> str:
    """Return an async SQLite URL for a temporary path."""
    return f"sqlite+aiosqlite:///{path}"


class RecordingEventPublisher:
    """Record every published event for assertions."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


def make_response(content: str) -> CompletionResponse:
    return CompletionResponse(
        model="gpt-test",
        content=content,
        usage=CompletionUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )


async def test_analyze_order_persists_tasks_and_audit_messages(tmp_path: Path) -> None:
    database = Database(sqlite_url(tmp_path / "analysis.db"))
    await database.initialize()
    transactions = SqlAlchemyWorkflowTransactionManager(database)
    order_intake = OrderIntakeService(
        transactions=transactions, events=RecordingEventPublisher()
    )
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(
        response=make_response(
            '[{"title": "Design"}, {"title": "Build", "depends_on": [0]}]'
        )
    )
    analysis = AnalysisService(
        transactions=transactions,
        order_intake=order_intake,
        provider=provider,
        model="gpt-test",
    )

    result = await analysis.analyze_order(intake.project_id)

    assert [task.title for task in result.tasks] == ["Design", "Build"]

    async with database.session() as session:
        tasks = await ProjectTaskRepository(session).list_by_project(intake.project_id)
        messages = await MessageRepository(session).list()
        conversations = await ConversationRepository(session).list()

    assert [task.title for task in tasks] == ["Design", "Build"]
    assert len(messages) == 3
    assert [message.role.value for message in messages] == ["system", "user", "agent"]
    assert all(message.conversation_id == conversations[0].id for message in messages)

    await database.close()


async def test_analyze_order_persists_audit_trail_but_no_tasks_on_malformed_response(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "malformed.db"))
    await database.initialize()
    transactions = SqlAlchemyWorkflowTransactionManager(database)
    order_intake = OrderIntakeService(
        transactions=transactions, events=RecordingEventPublisher()
    )
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(response=make_response("not valid json"))
    analysis = AnalysisService(
        transactions=transactions,
        order_intake=order_intake,
        provider=provider,
        model="gpt-test",
    )

    with pytest.raises(AnalysisResponseError):
        await analysis.analyze_order(intake.project_id)

    async with database.session() as session:
        tasks = await ProjectTaskRepository(session).list_by_project(intake.project_id)
        messages = await MessageRepository(session).list()

    assert tasks == []
    assert len(messages) == 3

    await database.close()


async def test_analyze_order_persists_nothing_when_provider_call_fails(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "provider-error.db"))
    await database.initialize()
    transactions = SqlAlchemyWorkflowTransactionManager(database)
    order_intake = OrderIntakeService(
        transactions=transactions, events=RecordingEventPublisher()
    )
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(error=ProviderTimeoutError("timed out"))
    analysis = AnalysisService(
        transactions=transactions,
        order_intake=order_intake,
        provider=provider,
        model="gpt-test",
    )

    with pytest.raises(ProviderTimeoutError):
        await analysis.analyze_order(intake.project_id)

    async with database.session() as session:
        tasks = await ProjectTaskRepository(session).list_by_project(intake.project_id)
        messages = await MessageRepository(session).list()

    assert tasks == []
    assert messages == []

    await database.close()


async def test_analyze_order_state_survives_database_recreation(tmp_path: Path) -> None:
    path = tmp_path / "survives.db"
    database = Database(sqlite_url(path))
    await database.initialize()
    transactions = SqlAlchemyWorkflowTransactionManager(database)
    order_intake = OrderIntakeService(
        transactions=transactions, events=RecordingEventPublisher()
    )
    intake = await order_intake.receive_order(
        OrderIntakeCommand(title="Build a shop", description="A small storefront")
    )
    provider = FakeCompletionProvider(response=make_response('[{"title": "Design"}]'))
    analysis = AnalysisService(
        transactions=transactions,
        order_intake=order_intake,
        provider=provider,
        model="gpt-test",
    )
    await analysis.analyze_order(intake.project_id)
    await database.close()

    second_database = Database(sqlite_url(path))
    await second_database.initialize()
    async with second_database.session() as session:
        tasks = await ProjectTaskRepository(session).list_by_project(intake.project_id)
        messages = await MessageRepository(session).list()

    assert [task.title for task in tasks] == ["Design"]
    assert len(messages) == 3

    await second_database.close()
