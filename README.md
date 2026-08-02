# Freelance Agents

Freelance Agents is an asynchronous Python foundation for a virtual company of
specialized agents. The project currently provides lifecycle models for a
company and its employees, a small in-process event bus, asynchronous SQLite
persistence with Alembic migrations, an `OrderIntakeService` application
service that accepts a client order and turns it into a project with a
validated task plan (see "Order intake and task workflow" below), and a
provider-neutral AI completion port with an OpenAI-compatible adapter and
usage/cost persistence (see "AI completion provider" below).

The project intentionally contains no freelance marketplace integrations,
Telegram bot, or business workflow that calls the AI provider yet; see
`docs/tasks/ROADMAP.md` for the planned sequence.

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
`FA_AI_BASE_URL`, `FA_AI_MODEL`, `FA_AI_TIMEOUT_SECONDS` (default `30`), and
`FA_AI_MAX_RETRIES` (default `2`).

Telegram settings are a placeholder for a future integration and may remain
empty for the current MVP. The AI completion provider is functional (see
below) but optional: `Application.completion_provider` is only constructed
when `FA_AI_API_KEY`, `FA_AI_BASE_URL`, and `FA_AI_MODEL` are all set, and is
`None` otherwise so the application still starts without them. Never commit
real keys, tokens, or passwords; `.env` files are ignored by Git.

`FA_LOG_LEVEL` controls standard-library logging and accepts `DEBUG`, `INFO`,
`WARNING`, or `ERROR`. Startup logs contain only the safe settings summary:
secret values are replaced by boolean configured/not-configured indicators.
Passwords embedded in database URLs are masked.

## Database

Persistence uses SQLAlchemy 2.x asynchronous APIs and SQLite through
`aiosqlite`. The default `FA_DATABASE_URL` stores state in
`data/freelance_agents.db`; local SQLite files are ignored by Git. Infrastructure
repositories provide create, read, update, and list operations for employees,
freelance orders, projects, conversations, messages, project events, ordered
project tasks, and AI completion provider calls.

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
or accept approvals — those are Issues #008–#011. See
`docs/ARCHITECTURE.md` for the transaction boundary and status-mapping
details.

## AI completion provider

`CompletionProvider` (`freelance_agents.core.providers`) is a provider-neutral
async port: `async def complete(request: CompletionRequest) -> CompletionResponse`.
No business workflow calls it yet (Issue #008 is the first consumer), and no
service or core type imports `httpx` or an AI SDK to define it.

`OpenAICompatibleProvider` (`freelance_agents.providers`) is the first
adapter. It talks to any HTTP API implementing the OpenAI chat-completions
shape, validates its `base_url`/`api_key` at construction, retries
429/5xx/timeout/connection failures up to `FA_AI_MAX_RETRIES` times with
exponential backoff bounded by `FA_AI_TIMEOUT_SECONDS` per call, raises
immediately (no retry) on 401/403 or another non-retryable 4xx, and never
logs the API key or message content.

`RecordingCompletionProvider` (`freelance_agents.database.provider_calls`)
decorates any `CompletionProvider`: it times each call, estimates cost via
`CostCalculator`, and persists one `provider_calls` row per attempt — model,
token usage, latency, status, and estimated cost, but never the prompt or
response text. `Application.completion_provider` is always this decorated
form when AI settings are configured.

`CostCalculator` has no built-in prices; construct it with a
`{model: ModelPricing(prompt_price_per_1k, completion_price_per_1k)}` table
of current rates. An unpriced model yields `estimated_cost=None` rather than
a guess. Tests use `tests/provider_fakes.FakeCompletionProvider` — a
`CompletionProvider` double that returns a canned response or raises a
canned `ProviderError` — instead of making real HTTP calls.

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
├── config/                # environment-backed infrastructure settings
├── database/               # async models, engine lifecycle, repositories,
│                          # the workflow ports adapter, and the provider
│                          # call recorder
├── logging_config.py    # standard logging setup
├── services/               # OrderIntakeService, ports, and DTOs
├── providers/               # OpenAI-compatible completion adapter
└── core/
    ├── company.py       # company aggregate
    ├── employees/       # employee model and status
    ├── events/          # event model and asynchronous event bus
    ├── workflow/          # order-intake and task-lifecycle domain types
    └── providers/          # completion port, normalized types, cost calculator
tests/                   # unit tests
docs/tasks/              # task scope and acceptance criteria
migrations/              # Alembic schema revisions
```
