"""Create the initial persistence schema.

Revision ID: 20260731_0001
Revises: None
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.Uuid()
UTC_DATETIME = sa.DateTime(timezone=True)


def timestamps() -> list[sa.Column[object]]:
    """Return shared UUID and timestamp migration columns."""
    return [
        sa.Column("id", UUID, nullable=False),
        sa.Column("created_at", UTC_DATETIME, nullable=False),
        sa.Column("updated_at", UTC_DATETIME, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    ]


def string_enum(name: str, *values: str) -> sa.Enum:
    """Create a portable constrained string enum."""
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    """Create all initial persistence tables."""
    op.create_table(
        "agents",
        *timestamps(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            string_enum("agent_status", "OFFLINE", "AVAILABLE", "BUSY"),
            nullable=False,
        ),
    )
    op.create_table(
        "freelance_orders",
        *timestamps(),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            string_enum(
                "order_status",
                "DRAFT",
                "OPEN",
                "ACCEPTED",
                "COMPLETED",
                "CANCELLED",
            ),
            nullable=False,
        ),
        sa.Column("budget", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.create_table(
        "projects",
        *timestamps(),
        sa.Column("order_id", UUID, nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            string_enum(
                "project_status",
                "PLANNED",
                "ACTIVE",
                "COMPLETED",
                "CANCELLED",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["freelance_orders.id"]),
    )
    op.create_index("ix_projects_order_id", "projects", ["order_id"])
    op.create_table(
        "conversations",
        *timestamps(),
        sa.Column("project_id", UUID, nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column(
            "status",
            string_enum("conversation_status", "OPEN", "ARCHIVED"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_index(
        "ix_conversations_project_id",
        "conversations",
        ["project_id"],
    )
    op.create_table(
        "messages",
        *timestamps(),
        sa.Column("conversation_id", UUID, nullable=False),
        sa.Column(
            "role",
            string_enum("message_role", "USER", "AGENT", "SYSTEM"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
    )
    op.create_index(
        "ix_messages_conversation_id",
        "messages",
        ["conversation_id"],
    )
    op.create_table(
        "project_events",
        *timestamps(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column(
            "event_type",
            string_enum(
                "project_event_type",
                "CREATED",
                "UPDATED",
                "STATUS_CHANGED",
                "COMPLETED",
            ),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_index(
        "ix_project_events_project_id",
        "project_events",
        ["project_id"],
    )


def downgrade() -> None:
    """Drop all persistence tables in dependency-safe order."""
    op.drop_index("ix_project_events_project_id", table_name="project_events")
    op.drop_table("project_events")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_project_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_projects_order_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("freelance_orders")
    op.drop_table("agents")
