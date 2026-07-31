# Issue #001 — Project foundation

## Goal

Create a minimal, runnable, and extensible Python 3.13 project using a modern
`src` layout and asynchronous lifecycle APIs.

## Implemented components

- `Employee` model with UUID identity, role, and lifecycle status.
- Immutable `Event` envelope with UTC timestamps.
- In-process asynchronous `EventBus` with named subscriptions.
- `Company` lifecycle coordinating employees and publishing events.
- `Application` composition root and module/console entry points.
- pytest test suite and Ruff linting/formatting configuration.

## Definition of done

- The package runs with both documented entry-point commands.
- Employees transition between offline and available states.
- Company start and stop operations coordinate all employees.
- Repeated company start and duplicate employee UUIDs are rejected.
- Events reach one or more async subscribers; unhandled events are valid.
- Tests, lint checks, and formatting checks pass.

## Deliberately out of scope

- Freelance order discovery or marketplace integrations.
- Telegram bot functionality.
- AI agent implementations or external AI SDKs.
- Database persistence, SQLAlchemy, and migrations.
- Long-running workers, scheduling, networking, or deployment infrastructure.
