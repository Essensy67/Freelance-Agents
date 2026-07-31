"""Shared SQLAlchemy declarations and persistence types."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist datetimes in UTC and restore timezone awareness."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        """Normalize bound datetime values to UTC."""
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Persisted datetimes must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        """Restore retrieved datetime values as UTC-aware values."""
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    """Base class for infrastructure persistence models."""
