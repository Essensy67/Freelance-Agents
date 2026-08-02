"""Add AI completion provider call persistence.

Revision ID: 20260802_0003
Revises: 20260802_0002
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0003"
down_revision: str | None = "20260802_0002"
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
    """Create the provider_calls table."""
    op.create_table(
        "provider_calls",
        *timestamps(),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            string_enum(
                "provider_call_status",
                "SUCCESS",
                "RATE_LIMITED",
                "TIMEOUT",
                "ERROR",
            ),
            nullable=False,
        ),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("error_type", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop the provider_calls table."""
    op.drop_table("provider_calls")
