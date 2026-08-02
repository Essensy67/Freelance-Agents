"""Async repositories for persisted project state."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from freelance_agents.database.base import Base, utc_now
from freelance_agents.database.models import (
    AgentModel,
    ConversationModel,
    ConversationStatus,
    FreelanceOrderModel,
    MessageModel,
    ProjectEventModel,
    ProjectModel,
    ProjectTaskModel,
)


class Repository[ModelT: Base]:
    """Provide common asynchronous CRUD operations for one model."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **values: Any) -> ModelT:
        """Create and flush a record in the current transaction."""
        record = self.model(**values)
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, record_id: UUID) -> ModelT | None:
        """Return a record by UUID, or none when it does not exist."""
        return await self.session.get(self.model, record_id)

    async def list(self) -> list[ModelT]:
        """List records in deterministic creation and UUID order."""
        statement = select(self.model).order_by(
            self.model.created_at,  # type: ignore[attr-defined]
            self.model.id,  # type: ignore[attr-defined]
        )
        return list((await self.session.scalars(statement)).all())

    async def update(self, record_id: UUID, **changes: Any) -> ModelT | None:
        """Update allowed mapped fields and flush the current transaction."""
        record = await self.get(record_id)
        if record is None:
            return None

        mapped_fields = set(self.model.__mapper__.columns.keys())
        immutable_fields = {"id", "created_at", "updated_at"}
        invalid_fields = set(changes) - mapped_fields | (
            set(changes) & immutable_fields
        )
        if invalid_fields:
            invalid = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Fields cannot be updated: {invalid}")

        for field_name, value in changes.items():
            setattr(record, field_name, value)
        record.updated_at = utc_now()  # type: ignore[attr-defined]
        await self.session.flush()
        return record


class AgentRepository(Repository[AgentModel]):
    """Persist employee records."""

    model = AgentModel


class FreelanceOrderRepository(Repository[FreelanceOrderModel]):
    """Persist freelance-order records."""

    model = FreelanceOrderModel

    async def get_by_client_request_key(
        self, request_key: str
    ) -> FreelanceOrderModel | None:
        """Return the order created with a given idempotency key, if any."""
        statement = select(self.model).where(
            self.model.client_request_key == request_key
        )
        return await self.session.scalar(statement)


class ProjectRepository(Repository[ProjectModel]):
    """Persist project records."""

    model = ProjectModel

    async def get_by_order_id(self, order_id: UUID) -> ProjectModel | None:
        """Return the project created for an order, if any."""
        statement = select(self.model).where(self.model.order_id == order_id)
        return await self.session.scalar(statement)


class ConversationRepository(Repository[ConversationModel]):
    """Persist conversation records."""

    model = ConversationModel

    async def get_open_for_project(self, project_id: UUID) -> ConversationModel | None:
        """Return the open conversation for a project, if any."""
        statement = (
            select(self.model)
            .where(
                self.model.project_id == project_id,
                self.model.status == ConversationStatus.OPEN,
            )
            .order_by(self.model.created_at)
        )
        return await self.session.scalar(statement)


class MessageRepository(Repository[MessageModel]):
    """Persist private message records."""

    model = MessageModel


class ProjectEventRepository(Repository[ProjectEventModel]):
    """Persist project event records."""

    model = ProjectEventModel


class ProjectTaskRepository(Repository[ProjectTaskModel]):
    """Persist ordered project task records."""

    model = ProjectTaskModel

    async def list_by_project(self, project_id: UUID) -> list[ProjectTaskModel]:
        """List a project's tasks in deterministic position order."""
        statement = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .order_by(self.model.position)
        )
        return list((await self.session.scalars(statement)).all())
