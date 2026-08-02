"""Add order intake idempotency key and project task persistence.

Revision ID: 20260802_0002
Revises: 20260731_0001
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0002"
down_revision: str | None = "20260731_0001"
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
    """Add order idempotency keys and the project_tasks table."""
    with op.batch_alter_table("freelance_orders") as batch_op:
        batch_op.add_column(
            sa.Column("client_request_key", sa.String(length=300), nullable=True)
        )
        batch_op.create_index(
            "ix_freelance_orders_client_request_key",
            ["client_request_key"],
            unique=True,
        )

    op.create_table(
        "project_tasks",
        *timestamps(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("capability", sa.String(length=200), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            string_enum(
                "project_task_status",
                "RECEIVED",
                "ACCEPTED",
                "PLANNING",
                "PLANNED",
                "IN_PROGRESS",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
            ),
            nullable=False,
        ),
        sa.Column("assigned_agent_id", UUID, nullable=True),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"]),
        sa.UniqueConstraint(
            "project_id", "position", name="uq_project_tasks_project_position"
        ),
    )
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"])


def downgrade() -> None:
    """Drop the project_tasks table and the order idempotency key."""
    op.drop_index("ix_project_tasks_project_id", table_name="project_tasks")
    op.drop_table("project_tasks")

    with op.batch_alter_table("freelance_orders") as batch_op:
        batch_op.drop_index("ix_freelance_orders_client_request_key")
        batch_op.drop_column("client_request_key")
