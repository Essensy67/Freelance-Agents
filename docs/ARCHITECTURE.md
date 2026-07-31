# Freelance Agents Architecture

## Purpose

Freelance Agents is an asynchronous foundation for a virtual freelance company
of specialized agents. Telegram is not the product boundary: it is only a
possible interface among future web, dashboard, and other interfaces.

## Current components

- **Employee** (`core.employees`) is a domain model with UUID identity, role,
  and lifecycle status.
- **Event** (`core.events.models`) is an immutable event envelope with a UUID
  and a UTC creation timestamp.
- **EventBus** (`core.events.bus`) delivers named events asynchronously to
  in-process subscribers.
- **Company** (`core.company`) coordinates employees and publishes lifecycle
  events when it starts and stops.
- **Application** (`application.py`) is the composition root: it creates the
  `EventBus` and `Company`, injects application settings, configures logging,
  and guarantees application startup and shutdown.
- **Config** (`config`) is an infrastructure layer that validates environment
  settings without introducing configuration dependencies into `core`.
- **CLI** (`__main__.py`) translates `SIGINT` and `SIGTERM` into cancellation
  of the active application lifecycle and removes its handlers on exit.
- **Logging configuration** (`logging_config.py`) configures Python logging
  from `Settings.log_level`; startup diagnostics use `Settings.safe_summary()`.
- **Database** (`database`) is an asynchronous SQLAlchemy infrastructure layer
  containing the engine/session lifecycle, transaction boundaries, ORM models,
  and repositories for durable company and project state.
- **Migrations** (`migrations`) version the database schema through Alembic.

## Dependency direction

The current dependency direction is:

```text
entry point (__main__) ──signals──→ Application → config (Settings)
                                         ├──────→ logging config
                                         ├──────→ database → SQLAlchemy/SQLite
                                         ↓
                                core (Company, EventBus, Event, Employee)
tests ──────────────────────────────────────────────────────────────────┘
```

`Application` loads or receives settings and assembles concrete dependencies.
The `config` and `database` layers are infrastructure and are never imported by
`core`. Repository transaction boundaries commit successful session contexts
and roll back exceptions. Domain code remains independent of delivery
interfaces and infrastructure. Future interfaces and integration adapters may
depend inward on application services and core; core must not depend outward on
Telegram, databases, SQLAlchemy, or concrete AI SDKs.

## Why core has no interface dependencies

The domain should express company behavior without knowing how a user invokes
it or where data is stored. Keeping Telegram, persistence, and provider SDKs
outside `core` makes the domain reusable from any interface, straightforward
to test offline, and less exposed to infrastructure changes.

## Running the application today

Run either documented entry point:

```bash
uv run python -m freelance_agents
uv run freelance-agents
```

The application initializes and health-checks persistence, logs a secret-safe
startup summary, starts the company, and guarantees company and database
shutdown in a `finally` block before exiting. The CLI handles `SIGINT` and
`SIGTERM` during this lifecycle. There is currently no background loop or
long-running interface.

## Persistence model

Infrastructure ORM models persist employees, freelance orders, projects,
conversations, private messages, and project events. They use UUID identifiers,
UTC timestamps, explicit status/role/event enums, and relational foreign keys.
These are persistence records rather than domain objects; future services may
map between them and core models without introducing outward core dependencies.

The application currently initializes the metadata for a new local database.
Alembic revision `20260731_0001` provides the equivalent versioned initial
schema for managed environments and supports downgrade to an empty schema.

## Issue #001 boundary

Issue #001 delivered the Python 3.13 `src` foundation, employee and company
lifecycle models, immutable UTC events, an asynchronous in-process event bus,
the application composition root, entry points, and unit tests. It explicitly
excluded marketplace integrations, Telegram, AI agents and external SDKs,
database persistence, workers, scheduling, networking, and deployment.

## Future layers (not implemented)

The intended structure reserves space for:

- `services` for application use cases and integrations;
- `app` for interface adapters and entry points;
- `database` for persistence and migrations;
- additional interface and infrastructure adapters as the product grows.

These layers are architectural boundaries only; Issues #001 and #002 did not
implement them or add any of their dependencies. Issue #003 adds only the
infrastructure `config` layer described above; Issue #004 adds logging and
orderly application lifecycle handling without introducing integrations. Issue
#005 adds asynchronous persistence and migrations while keeping SQLAlchemy out
of `core`.
