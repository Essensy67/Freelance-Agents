# Freelance Agents

Freelance Agents is an asynchronous Python foundation for a virtual company of
specialized agents. The project currently provides lifecycle models for a
company and its employees, a small in-process event bus, asynchronous SQLite
persistence with Alembic migrations, and an `OrderIntakeService` application
service that accepts a client order and turns it into a project with a
validated task plan (see "Order intake and task workflow" below).

The project intentionally contains no freelance marketplace integrations,
Telegram bot, or AI provider calls yet; see `docs/tasks/ROADMAP.md` for the
planned sequence.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync
```

## Running

Run the Python module:

```bash
uv run python -m freelance_agents
```

Or use the installed console command:

```bash
uv run freelance-agents
```

The current one-shot MVP initializes and health-checks its database, logs its
safe startup configuration, starts the company, and always shuts down both the
company and database engine before exiting. During the lifecycle, `SIGINT` and
`SIGTERM` request orderly cancellation and cleanup.

## Configuration

The application uses `FA_`-prefixed environment variables and can read an
optional local `.env` file. Start from the safe example:

```bash
cp .env.example .env
```

The main variables are `FA_APP_NAME`, `FA_ENVIRONMENT`, `FA_DEBUG`,
`FA_LOG_LEVEL`, `FA_DATABASE_URL`, `FA_TELEGRAM_BOT_TOKEN`, `FA_AI_API_KEY`,
`FA_AI_BASE_URL`, and `FA_AI_MODEL`.

Telegram and AI settings are placeholders for future integrations. Their
values may remain empty for the current MVP. Never commit real keys, tokens,
or passwords; `.env` files are ignored by Git.

`FA_LOG_LEVEL` controls standard-library logging and accepts `DEBUG`, `INFO`,
`WARNING`, or `ERROR`. Startup logs contain only the safe settings summary:
secret values are replaced by boolean configured/not-configured indicators.
Passwords embedded in database URLs are masked.

## Database

Persistence uses SQLAlchemy 2.x asynchronous APIs and SQLite through
`aiosqlite`. The default `FA_DATABASE_URL` stores state in
`data/freelance_agents.db`; local SQLite files are ignored by Git. Infrastructure
repositories provide create, read, update, and list operations for employees,
freelance orders, projects, conversations, messages, project events, and
ordered project tasks.

## Order intake and task workflow

`OrderIntakeService` (`freelance_agents.services`) is the first
application-service vertical slice. It exposes four transport-neutral
operations, used by `Application.order_intake_service` and available to any
future interface without that interface touching SQLAlchemy or ORM models:

- `receive_order(command)` — validates a title, description, and optional
  budget, then creates an order, project, open conversation, and intake
  event in one transaction. Repeating the same `request_key` with equivalent
  content returns the original result instead of creating duplicates.
- `create_plan(project_id, plan)` — replaces an unplanned project's task list
  with a validated, ordered set of tasks; rejects blank titles, duplicate
  task ids, and dangling dependency references.
- `get_project_workflow(project_id)` — returns the current order/project
  status and task list.
- `transition_task(task_id, target_status)` — moves one task through
  `received → accepted → planning → planned → in_progress → completed` (with
  `failed`/`cancelled` reachable from any non-terminal state), rejecting
  skipped states or a mutated terminal task.

This service does not call an AI provider, assign employees, execute tasks,
or accept approvals — those are Issues #007–#011. See
`docs/ARCHITECTURE.md` for the transaction boundary and status-mapping
details.

Apply the versioned schema migration with:

```bash
uv run alembic upgrade head
```

Inspect the current revision or roll the schema back with:

```bash
uv run alembic current
uv run alembic downgrade base
```

Alembic reads the same `FA_DATABASE_URL` setting as the application. Private
message bodies and database credentials are not written to application logs.

## Development

Run the tests:

```bash
uv run pytest
```

Check linting and formatting:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Project structure

```text
src/freelance_agents/
├── __main__.py          # CLI entry point
├── application.py       # dependency composition and lifecycle
├── config/               # environment-backed infrastructure settings
├── database/             # async models, engine lifecycle, repositories,
│                         # and the workflow ports adapter
├── logging_config.py    # standard logging setup
├── services/             # OrderIntakeService, ports, and DTOs
└── core/
    ├── company.py       # company aggregate
    ├── employees/       # employee model and status
    ├── events/          # event model and asynchronous event bus
    └── workflow/         # order-intake and task-lifecycle domain types
tests/                   # unit tests
docs/tasks/              # task scope and acceptance criteria
migrations/              # Alembic schema revisions
```
