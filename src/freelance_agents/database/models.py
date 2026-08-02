"""Infrastructure models for persisted virtual-company state."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
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


class ProjectTaskStatus(StrEnum):
    """Persisted lifecycle states for one project task.

    Mirrors ``core.workflow.statuses.TaskStatus``; the adapter in
    ``database.workflow`` converts between the two by value.
    """

    RECEIVED = "received"
    ACCEPTED = "accepted"
    PLANNING = "planning"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProviderCallStatus(StrEnum):
    """Persisted outcome of one AI completion provider call."""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    ERROR = "error"


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
    client_request_key: Mapped[str | None] = mapped_column(String(300), nullable=True)


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


class ProjectTaskModel(TimestampedModel, Base):
    """Persist one ordered unit of work belonging to a project."""

    __tablename__ = "project_tasks"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "position", name="uq_project_tasks_project_position"
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id")
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    capability: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[ProjectTaskStatus] = mapped_column(
        Enum(
            ProjectTaskStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="project_task_status",
        ),
        default=ProjectTaskStatus.RECEIVED,
    )
    assigned_agent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id"),
        nullable=True,
    )
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list)


class ProviderCallModel(TimestampedModel, Base):
    """Persist one AI completion provider call without its prompt/response body."""

    __tablename__ = "provider_calls"

    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    status: Mapped[ProviderCallStatus] = mapped_column(
        Enum(
            ProviderCallStatus,
            native_enum=False,
            validate_strings=True,
            create_constraint=True,
            name="provider_call_status",
        )
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    error_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


Index("ix_projects_order_id", ProjectModel.order_id)
Index("ix_conversations_project_id", ConversationModel.project_id)
Index("ix_messages_conversation_id", MessageModel.conversation_id)
Index("ix_project_events_project_id", ProjectEventModel.project_id)
Index("ix_project_tasks_project_id", ProjectTaskModel.project_id)
Index(
    "ix_freelance_orders_client_request_key",
    FreelanceOrderModel.client_request_key,
    unique=True,
)
