"""Asynchronous database lifecycle and transaction boundaries."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from freelance_agents.database.base import Base


class Database:
    """Own the async engine, schema initialization, and transactions."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def is_initialized(self) -> bool:
        """Return whether an engine and session factory are active."""
        return self._engine is not None and self._session_factory is not None

    async def initialize(self) -> None:
        """Create the async engine and initialize the current schema."""
        if self.is_initialized:
            return
        self._prepare_sqlite_directory()
        self._engine = create_async_engine(self.database_url)
        if make_url(self.database_url).drivername.startswith("sqlite"):
            event.listen(self._engine.sync_engine, "connect", _enable_foreign_keys)
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )
        try:
            async with self._engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        except BaseException:
            await self.close()
            raise

    async def health_check(self) -> bool:
        """Verify that the initialized database can execute a query."""
        if self._engine is None:
            return False
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            return False
        return True

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a transactional session with commit or rollback."""
        if self._session_factory is None:
            raise RuntimeError("Database is not initialized")
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Dispose the async engine and clear lifecycle state."""
        engine = self._engine
        self._engine = None
        self._session_factory = None
        if engine is not None:
            await engine.dispose()

    def _prepare_sqlite_directory(self) -> None:
        url = make_url(self.database_url)
        if not url.drivername.startswith("sqlite"):
            return
        database = url.database
        if not database or database == ":memory:":
            return
        Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
    """Enable SQLite foreign-key enforcement for every connection."""
    del connection_record
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
