from datetime import UTC
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text

from freelance_agents.database import (
    AgentRepository,
    AgentStatus,
    ConversationRepository,
    ConversationStatus,
    Database,
    FreelanceOrderRepository,
    MessageRepository,
    MessageRole,
    OrderStatus,
    ProjectEventRepository,
    ProjectEventType,
    ProjectRepository,
    ProjectStatus,
)


def sqlite_url(path: Path) -> str:
    """Return an async SQLite URL for a temporary path."""
    return f"sqlite+aiosqlite:///{path}"


async def test_repositories_create_read_update_and_list_all_records(
    tmp_path: Path,
) -> None:
    database = Database(sqlite_url(tmp_path / "records.db"))
    await database.initialize()

    async with database.session() as session:
        agent_repository = AgentRepository(session)
        order_repository = FreelanceOrderRepository(session)
        project_repository = ProjectRepository(session)
        conversation_repository = ConversationRepository(session)
        message_repository = MessageRepository(session)
        event_repository = ProjectEventRepository(session)

        agent = await agent_repository.create(
            name="Alex",
            role="Developer",
            status=AgentStatus.AVAILABLE,
        )
        order = await order_repository.create(
            title="Build an application",
            description="Private order details",
            status=OrderStatus.OPEN,
            budget=Decimal("1250.00"),
        )
        project = await project_repository.create(
            order_id=order.id,
            name="Application project",
            description="Project state",
            status=ProjectStatus.ACTIVE,
        )
        conversation = await conversation_repository.create(
            project_id=project.id,
            title="Client conversation",
            status=ConversationStatus.OPEN,
        )
        message = await message_repository.create(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Private message contents",
        )
        project_event = await event_repository.create(
            project_id=project.id,
            event_type=ProjectEventType.CREATED,
            payload={"source": "test"},
        )

        updated_agent = await agent_repository.update(
            agent.id,
            status=AgentStatus.BUSY,
        )
        updated_order = await order_repository.update(
            order.id,
            status=OrderStatus.ACCEPTED,
        )
        updated_project = await project_repository.update(
            project.id,
            status=ProjectStatus.COMPLETED,
        )
        updated_conversation = await conversation_repository.update(
            conversation.id,
            status=ConversationStatus.ARCHIVED,
        )
        updated_message = await message_repository.update(
            message.id,
            role=MessageRole.AGENT,
        )
        updated_event = await event_repository.update(
            project_event.id,
            event_type=ProjectEventType.UPDATED,
        )

        assert updated_agent is not None
        assert updated_agent.status is AgentStatus.BUSY
        assert updated_order is not None
        assert updated_order.status is OrderStatus.ACCEPTED
        assert updated_project is not None
        assert updated_project.status is ProjectStatus.COMPLETED
        assert updated_conversation is not None
        assert updated_conversation.status is ConversationStatus.ARCHIVED
        assert updated_message is not None
        assert updated_message.role is MessageRole.AGENT
        assert updated_event is not None
        assert updated_event.event_type is ProjectEventType.UPDATED

        assert await agent_repository.get(agent.id) is agent
        assert await agent_repository.list() == [agent]
        assert await order_repository.list() == [order]
        assert await project_repository.list() == [project]
        assert await conversation_repository.list() == [conversation]
        assert await message_repository.list() == [message]
        assert await event_repository.list() == [project_event]
        assert isinstance(agent.id, UUID)
        assert agent.created_at.tzinfo is UTC
        assert agent.updated_at.tzinfo is UTC

    await database.close()


async def test_failed_transaction_rolls_back(tmp_path: Path) -> None:
    database = Database(sqlite_url(tmp_path / "rollback.db"))
    await database.initialize()

    with pytest.raises(RuntimeError, match="transaction failed"):
        async with database.session() as session:
            await AgentRepository(session).create(
                name="Rollback Agent",
                role="Tester",
            )
            raise RuntimeError("transaction failed")

    async with database.session() as session:
        assert await AgentRepository(session).list() == []

    await database.close()


async def test_data_persists_after_database_recreation(tmp_path: Path) -> None:
    path = tmp_path / "persistent.db"
    first_database = Database(sqlite_url(path))
    await first_database.initialize()
    async with first_database.session() as session:
        agent = await AgentRepository(session).create(
            name="Persistent Agent",
            role="Developer",
        )
        agent_id = agent.id
    await first_database.close()

    second_database = Database(sqlite_url(path))
    await second_database.initialize()
    async with second_database.session() as session:
        restored = await AgentRepository(session).get(agent_id)

        assert restored is not None
        assert restored.name == "Persistent Agent"
        assert restored.status is AgentStatus.OFFLINE
    await second_database.close()


async def test_health_check_and_close_lifecycle(tmp_path: Path) -> None:
    database = Database(sqlite_url(tmp_path / "health.db"))

    assert await database.health_check() is False
    await database.initialize()
    assert database.is_initialized is True
    assert await database.health_check() is True

    async with database.session() as session:
        assert await session.scalar(text("SELECT 1")) == 1

    await database.close()
    assert database.is_initialized is False
    assert await database.health_check() is False


async def test_update_rejects_immutable_or_unknown_fields(tmp_path: Path) -> None:
    database = Database(sqlite_url(tmp_path / "updates.db"))
    await database.initialize()
    async with database.session() as session:
        repository = AgentRepository(session)
        agent = await repository.create(name="Agent", role="Developer")

        with pytest.raises(ValueError, match="id, unknown"):
            await repository.update(agent.id, id=agent.id, unknown="value")

    await database.close()
