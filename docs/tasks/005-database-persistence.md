# Issue #005 — Database persistence and project state

## Goal

Add an asynchronous SQLite persistence layer that preserves virtual-company
state across application and repository recreation.

## Architecture

- `database` is an infrastructure package based on SQLAlchemy 2.x async APIs.
- `core` does not import SQLAlchemy or database modules.
- `Application` owns the database lifecycle and constructs it from
  `Settings.database_url`.
- Repositories receive an `AsyncSession`; transaction boundaries belong to the
  database session context manager.
- Alembic is the versioned schema migration mechanism.

## Persistent records

The initial schema stores employees, freelance orders, projects,
conversations, messages, and project events. Records use UUID primary keys, UTC
timestamps, foreign keys where applicable, and explicit enums for lifecycle,
role, and event-type values. Each repository supports create, read, update, and
list operations.

## Transactions and lifecycle

- Successful session contexts commit automatically.
- Exceptions roll back the transaction and remain visible to callers.
- Application startup initializes the database schema and runs a health check
  before starting the company.
- Application shutdown closes the database engine even when company shutdown
  fails.

## Privacy and logging

Database credentials and private message contents are never logged. Lifecycle
logs contain only operational status. Existing settings summaries continue to
exclude secrets.

## Migration

The initial Alembic revision creates all six tables, enum constraints, indexes,
and foreign keys. Downgrade removes the tables in dependency-safe order.

## Definition of done

- Async SQLite persistence works through SQLAlchemy 2.x and aiosqlite.
- CRUD/list operations and explicit statuses are covered by isolated tests.
- Failed transactions roll back.
- Data survives repository, session, engine, and application recreation.
- Database initialize, health check, and close are application-owned.
- The initial Alembic migration upgrades and downgrades a temporary database.
- pytest, Ruff, both entry points, and Git whitespace checks pass.

## Deliberately out of scope

- Telegram, AI providers, marketplace integrations, or business agents.
- Marketplace order discovery or synchronization.
- Encryption-at-rest, access control, retention policies, or message search.
- PostgreSQL-specific behavior, deployment automation, or hosted migrations.
