"""Infrastructure models for persisted virtual-company state."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Enum, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from freelance_agents.database.base import Base, UTCDateTime, utc_now


class AgentStatus(StrEnum):
    """Persisted employee availability states."""

    OFFLINE = "offline"
    AVAILABLE = "available"
    BUSY = "busy"


class OrderStatus(StrEnum):
    """Persisted freelance-order lifecycle states."""

    DRAFT = "draft"
    OPEN = "open"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectStatus(StrEnum):
    """Persisted project lifecycle states."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConversationStatus(StrEnum):
    """Persisted conversation lifecycle states."""

    OPEN = "open"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    """Supported authorship roles for persisted messages."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class ProjectEventType(StrEnum):
    """Supported persisted project event types."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    COMPLETED = "completed"


class TimestampedModel:
    """Provide UUID identity and UTC timestamps to persisted records."""

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        onupdate=utc_now,
    )


class AgentModel(TimestampedModel, Base):
    """Persist an employee record independently from the core model."""

    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    status: Mapped[AgentStatus] = mapped_column(
        Enum(
            AgentStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="agent_status",
        ),
        default=AgentStatus.OFFLINE,
    )


class FreelanceOrderModel(TimestampedModel, Base):
    """Persist a freelance order without marketplace integration details."""

    __tablename__ = "freelance_orders"

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="order_status",
        ),
        default=OrderStatus.DRAFT,
    )
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)


class ProjectModel(TimestampedModel, Base):
    """Persist a project and its optional source order."""

    __tablename__ = "projects"

    order_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("freelance_orders.id"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="project_status",
        ),
        default=ProjectStatus.PLANNED,
    )


class ConversationModel(TimestampedModel, Base):
    """Persist a project conversation."""

    __tablename__ = "conversations"

    project_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(
            ConversationStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="conversation_status",
        ),
        default=ConversationStatus.OPEN,
    )


class MessageModel(TimestampedModel, Base):
    """Persist private conversation message content."""

    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id"),
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="message_role",
        )
    )
    content: Mapped[str] = mapped_column(Text)


class ProjectEventModel(TimestampedModel, Base):
    """Persist structured project history without logging its payload."""

    __tablename__ = "project_events"

    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id"),
    )
    event_type: Mapped[ProjectEventType] = mapped_column(
        Enum(
            ProjectEventType,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="project_event_type",
        )
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


Index("ix_projects_order_id", ProjectModel.order_id)
Index("ix_conversations_project_id", ConversationModel.project_id)
Index("ix_messages_conversation_id", MessageModel.conversation_id)
Index("ix_project_events_project_id", ProjectEventModel.project_id)
