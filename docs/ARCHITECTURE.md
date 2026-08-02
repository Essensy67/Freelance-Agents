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
  and repositories for durable company and project state, plus the
  `database.workflow` adapter described below.
- **Migrations** (`migrations`) version the database schema through Alembic.
- **Core workflow types** (`core.workflow`) are SQLAlchemy-free domain types
  for order intake and task lifecycle: `OrderDetails` and `TaskPlan` validate
  input, `TaskStatus` and `ensure_valid_task_transition` enforce legal task
  moves, `OrderIntakeStatus`/`ProjectWorkflowStatus` mirror the persisted
  order/project status values, and `OrderRecord`/`ProjectRecord`/
  `ConversationRecord`/`TaskRecord` are plain read-model records returned by
  repository ports.
- **Services** (`services`) hosts `OrderIntakeService`, the first
  application-service vertical slice (Issue #006). It depends only on the
  `WorkflowTransactionManager`/`WorkflowUnitOfWork` and `EventPublisherPort`
  protocols in `services.ports`, plus `core.workflow` types — never on
  SQLAlchemy. `services.dto` holds its transport-neutral commands and
  results (`OrderIntakeCommand`/`OrderIntakeResult`, `PlanCommand`/
  `PlanResult`, `WorkflowSnapshot`).
- **Workflow adapter** (`database.workflow`) implements the `services.ports`
  protocols with the SQLAlchemy repositories, translating ORM models to and
  from `core.workflow` records. `SqlAlchemyWorkflowTransactionManager.begin()`
  wraps one `Database.session()` call per unit of work, so a transaction
  boundary spans exactly one `OrderIntakeService` operation.
- **Core provider types** (`core.providers`) are SQLAlchemy/SDK-free domain
  types for AI completions (Issue #007): `CompletionRequest`/
  `CompletionResponse`/`CompletionUsage`/`CompletionMessage` normalize a
  completion call, `CompletionProvider` is the async port any future service
  depends on, `ProviderError` and its subclasses are the typed failure
  vocabulary, and `CostCalculator`/`ModelPricing` estimate cost from usage
  and an injected pricing table (no hardcoded prices).
- **Provider adapter** (`providers.openai_compatible`) implements
  `CompletionProvider` over any OpenAI-compatible chat-completions HTTP API
  using `httpx`. It validates its configuration eagerly, retries transient
  failures (429/5xx/timeout/connection errors) with exponential backoff,
  raises immediately on non-retryable 4xx responses, and never logs the API
  key or message content.
- **Provider call recorder** (`database.provider_calls`) is
  `RecordingCompletionProvider`, a decorator that also implements
  `CompletionProvider`. It times every call, estimates its cost, and
  persists one `provider_calls` row per attempt (success or failure) without
  storing prompt/response content; a persistence failure is logged and
  swallowed so it never masks the underlying provider result or error.

## Dependency direction

The current dependency direction is:

```text
entry point (__main__) ──signals──→ Application → config (Settings)
                                         ├──────→ logging config
                                         ├──────→ database → SQLAlchemy/SQLite
                                         ├──────→ database.workflow → services.ports (adapter)
                                         ├──────→ services (OrderIntakeService) → core.workflow
                                         ├──────→ providers.openai_compatible → httpx (adapter)
                                         ├──────→ database.provider_calls → core.providers (adapter)
                                         ↓
                                core (Company, EventBus, Event, Employee, providers)
tests ──────────────────────────────────────────────────────────────────┘
```

`Application` loads or receives settings and assembles concrete dependencies,
including `order_intake_service = OrderIntakeService(transactions=
SqlAlchemyWorkflowTransactionManager(database), events=event_bus)` and,
when `ai_api_key`/`ai_base_url`/`ai_model` are all configured,
`completion_provider = RecordingCompletionProvider(OpenAICompatibleProvider(...),
database, CostCalculator(), provider_name="openai_compatible")`; otherwise
`completion_provider` is `None` so the application still starts without AI
credentials. The `config`, `database`, `services`, and `providers` layers
are infrastructure/application layers and are never imported by `core`.
`services` and `core.providers` depend inward on `core` only — neither
imports `database`, `httpx`, or a concrete AI SDK, which lets
`OrderIntakeService` run against the in-memory fakes in
`tests/workflow_fakes.py` and lets any future consumer of
`CompletionProvider` run against `tests/provider_fakes.py`.
`database.workflow` and `database.provider_calls` are the two places that
depend on both an application/core port (to implement it) and SQLAlchemy (to
fulfil it), consistent with "adapters depend inward on services and core."
Repository transaction boundaries commit successful session contexts and
roll back exceptions; `SqlAlchemyWorkflowTransactionManager.begin()` uses the
same `Database.session()` commit/rollback behavior, and
`RecordingCompletionProvider` opens one such session per call it records.
Domain code remains independent of delivery interfaces and infrastructure.
Future interfaces depend inward on `services` and `core`; core must not
depend outward on Telegram, databases, SQLAlchemy, or concrete AI SDKs.

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
conversations, private messages, project events, and (since Issue #006)
project tasks. They use UUID identifiers, UTC timestamps, explicit
status/role/event enums, and relational foreign keys. These are persistence
records rather than domain objects; `database.workflow` maps between them and
`core.workflow` records without introducing outward core dependencies.

The application currently initializes the metadata for a new local database.
Alembic revision `20260731_0001` provides the equivalent versioned initial
schema for managed environments; revision `20260802_0002` adds the
`freelance_orders.client_request_key` idempotency column and the
`project_tasks` table; revision `20260802_0003` adds the `provider_calls`
table. All three support downgrade back to an empty schema.

### Order intake and task workflow (Issue #006)

`project_tasks` stores one ordered unit of work per row: `id`, `created_at`,
`updated_at`, an indexed `project_id` foreign key, `title`, `description`, an
optional `capability` (unused until Issue #009's agent catalog), an integer
`position` for deterministic ordering, a constrained `status` string, an
optional `assigned_agent_id` foreign key (unused until Issue #009's
assignment service), and a `depends_on` JSON list of task UUIDs validated
against the same plan by `TaskPlan.create` before persistence. A unique
constraint on `(project_id, position)` prevents position collisions.

`ProjectTaskStatus` (persisted) and `TaskStatus` (core-facing) share the
lifecycle `received → accepted → planning → planned → in_progress →
completed`, with `failed` and `cancelled` reachable from any non-terminal
state; `ensure_valid_task_transition` rejects skipped states and mutation of
a terminal task. This vocabulary belongs to individual tasks, not to the
order or project: `freelance_orders.status` and `projects.status` keep their
Issue #005 enums unchanged. `OrderIntakeService.receive_order` persists a new
order as `OrderStatus.OPEN` (mirrored as `OrderIntakeStatus.OPEN`) and its
project as `ProjectStatus.PLANNED` (mirrored as
`ProjectWorkflowStatus.PLANNED`); neither advances further within this issue
— activation and completion are introduced by Issues #010 and #011.

`freelance_orders.client_request_key` is a nullable column with a unique
index over non-null values (SQLite unique indexes, like standard SQL, treat
`NULL` values as distinct, so orders without a request key never collide).
`receive_order` looks the key up first: an equivalent repeat (same title,
description, and budget) returns the original order/project/conversation
without creating duplicates; a repeat with different content raises
`IdempotencyConflictError`.

`receive_order` and `create_plan` each run inside exactly one
`SqlAlchemyWorkflowTransactionManager.begin()` unit of work — order, project,
conversation, and intake event (or the full task list) are created together
or not at all, matching the existing `Database.session()` commit/rollback
contract. Domain/application events (`order.received`, `project.created`,
`plan.created`) are published on the shared `EventBus` only after that
transaction commits; a publish failure is logged and re-raised to the
caller, consistent with how `Application.shutdown` already surfaces lifecycle
errors. Issue #014 may replace this direct-publish policy with an outbox.
Published event payloads carry only IDs and statuses, never order titles,
descriptions, or other private content.

### AI provider calls and usage accounting (Issue #007)

`provider_calls` stores one row per completion attempt: `id`, `created_at`,
`updated_at`, `provider` (adapter name, e.g. `openai_compatible`), `model`,
a constrained `status` (`success`/`rate_limited`/`timeout`/`error`),
`prompt_tokens`/`completion_tokens`/`total_tokens`, `latency_ms`, a nullable
`estimated_cost`, and nullable `error_type`/`error_message`. It never stores
prompt or response text — only metadata, consistent with the redaction
policy already applied to `project_events` payloads.

`CompletionProvider` is the only type any future service (Issue #008's
analysis service is the first consumer) depends on; nothing in `core` or
`services` imports `httpx` or an AI SDK. `OpenAICompatibleProvider`
(`providers.openai_compatible`) is the first concrete adapter: it validates
`base_url`/`api_key` are non-blank at construction, retries 429/5xx/timeout/
connection failures up to `Settings.ai_max_retries` times with exponential
backoff (`Settings.ai_timeout_seconds` bounds each HTTP call), and raises
immediately — without retrying — on 401/403 (`ProviderAuthenticationError`)
or another non-retryable 4xx (`ProviderResponseError`). `RecordingCompletionProvider`
(`database.provider_calls`) wraps any `CompletionProvider`, so recording is
an orthogonal decorator rather than something each adapter implements itself;
`Application` always composes the two together when AI settings are present.

`CostCalculator` estimates cost from an explicit, injected
`Mapping[str, ModelPricing]`; it has no built-in prices (real rates change
and vary by deployment) and returns `None` for an unpriced model rather than
guessing, so `provider_calls.estimated_cost` is honestly nullable. Issue
#016 is where a durable, operator-managed price table belongs.

`Settings` gained `ai_timeout_seconds` (default `30.0`) and `ai_max_retries`
(default `2`); together with the existing `ai_api_key`/`ai_base_url`/
`ai_model`, all three must be set for `Application.completion_provider` to
be constructed — otherwise it is `None` and the application still starts,
matching the existing "AI settings are optional placeholders for the
current MVP" policy.

## Issue #001 boundary

Issue #001 delivered the Python 3.13 `src` foundation, employee and company
lifecycle models, immutable UTC events, an asynchronous in-process event bus,
the application composition root, entry points, and unit tests. It explicitly
excluded marketplace integrations, Telegram, AI agents and external SDKs,
database persistence, workers, scheduling, networking, and deployment.

## Future layers (not yet implemented)

The intended structure still reserves space for:

- `app` for interface adapters and entry points (Telegram in Issue #012, an
  optional web UI in Issue #013);
- additional provider adapters and infrastructure adapters as the product
  grows (Issue #018).

`services` for application use cases now exists as of Issue #006, scoped to
order intake and task workflow; `providers`/`core.providers` for AI
completions now exist as of Issue #007. Later issues extend these layers
rather than introducing parallel ones.

These layers are architectural boundaries only; Issues #001 and #002 did not
implement them or add any of their dependencies. Issue #003 adds only the
infrastructure `config` layer described above; Issue #004 adds logging and
orderly application lifecycle handling without introducing integrations.
Issue #005 adds asynchronous persistence and migrations while keeping
SQLAlchemy out of `core`. Issue #006 adds the `services` application layer,
`core.workflow` domain types, and `project_tasks` persistence, without adding
provider credentials, decomposition, assignment, execution, approval, or any
interface adapter. Issue #007 adds the `CompletionProvider` port, its
OpenAI-compatible adapter, usage/cost persistence, and a fake for tests,
without adding a business workflow that calls it, retry/queueing beyond the
adapter's own policy, or a real pricing table — those remain scoped to
Issues #008–#018.
