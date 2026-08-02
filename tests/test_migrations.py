from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_upgrades_and_downgrades(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "migration.db"
    async_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("FA_DATABASE_URL", async_url)
    config = Config("alembic.ini")

    command.upgrade(config, "head")

    sync_engine = create_engine(f"sqlite:///{database_path}")
    assert set(inspect(sync_engine).get_table_names()) == {
        "agents",
        "alembic_version",
        "conversations",
        "freelance_orders",
        "messages",
        "project_events",
        "project_tasks",
        "projects",
        "provider_calls",
    }
    sync_engine.dispose()

    command.downgrade(config, "base")

    sync_engine = create_engine(f"sqlite:///{database_path}")
    assert inspect(sync_engine).get_table_names() == ["alembic_version"]
    sync_engine.dispose()
