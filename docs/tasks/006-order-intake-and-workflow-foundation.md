# Issue #006 — Order intake and workflow foundation

## Goal

Establish the first application-service vertical slice after the persistence
foundation: accept a client order through a transport-independent use case,
create the corresponding project and conversation, and persist a validated
work plan as tasks. This issue defines the contracts and state transitions
that Issues #007–#012 will extend. It does not call an AI provider and does
not add Telegram or a web server.

## Why this is first

Issue #005 provides generic records and CRUD repositories, but no business
operation owns their lifecycle or relates them as one workflow. Provider calls,
assignment, execution, approval, and interfaces all need a stable project/task
identity, status vocabulary, idempotency behavior, and service boundary.
Implementing those rules first keeps adapters thin and makes the rest of the
MVP testable offline.

## Scope

- Add an application `services` package with transport-neutral DTOs and an
  `OrderIntakeService` (or equivalent clearly named use-case service).
- Add core value objects/enums for order intake and task lifecycle without
  importing SQLAlchemy, Telegram, or an AI SDK into `core`.
- Extend persistence with a migration and repository for ordered project
  tasks. A task must have a UUID, project, title, description, position,
  required capability (optional for this issue), status, and timestamps.
- Define the minimum statuses and legal transitions:
  `received → accepted → planning → planned → in_progress → completed`, with
  `failed` and `cancelled` terminal/error paths. The order and project may
  retain their existing statuses; document the mapping rather than silently
  changing Issue #005 enums.
- Accept a client order containing a non-empty title and description and an
  optional budget and external/idempotency key.
- In one transaction, create or return the order, project, initial open
  conversation, and a persisted intake event. Repeating the same idempotency
  key must return the original aggregate without duplicate records.
- Add a separate operation to replace a draft/received plan with a validated,
  ordered list of tasks. It must reject empty titles, duplicate task IDs (if
  supplied), invalid dependency references, and illegal status changes.
- Publish application/domain events after successful commits (for example
  `order.received`, `project.created`, and `plan.created`) without putting
  database calls in event handlers.
- Update architecture documentation and README structure notes to mention the
  service layer and task persistence.

## Explicit non-goals

- No provider credentials, HTTP calls, model SDKs, prompt templates, or cost
  calculation (Issue #007).
- No automatic decomposition of natural language (Issue #008).
- No real employee assignment or execution worker (Issues #009–#010).
- No approval, delivery, Telegram, web, authentication, billing, files, or
  marketplace integration.
- No broad rewrite of the generic repositories or existing core lifecycle.

## Proposed boundaries

`services` owns use-case orchestration and transaction-facing ports. A service
may depend on repository protocols and an event publisher protocol; concrete
SQLAlchemy repositories and the existing `EventBus` are assembled in
`Application`. `core` contains only business types and transition rules.
Database models remain persistence records and are mapped at the boundary.
The interface added in later issues calls service methods and receives DTOs;
it never constructs ORM models.

Suggested operations (names may change if equivalent behavior is preserved):

```text
receive_order(command) -> OrderIntakeResult
create_plan(project_id, plan) -> PlanResult
get_project_workflow(project_id) -> WorkflowSnapshot
transition_task(task_id, target_status) -> TaskResult
```

`OrderIntakeResult` should expose stable IDs, statuses, and timestamps, not ORM
objects. Commands must be immutable or otherwise safe to retry.

## Persistence design

Add a `project_tasks` table (or an equally clear name) with:

- `id`, `created_at`, `updated_at`;
- `project_id` foreign key and an index;
- `title`, `description`, and optional `capability`;
- integer `position` for deterministic ordering;
- constrained status string and optional `assigned_agent_id` foreign key;
- optional `depends_on` representation only if it can be validated without
  introducing a premature graph subsystem. A JSON list of task UUIDs is
  acceptable for this issue if repository validation prevents dangling IDs.
- a unique constraint for `(project_id, position)` and, when present, the
  intake idempotency key on orders.

If the existing `freelance_orders` table has no idempotency column, add a
backward-compatible nullable `client_request_key` with a unique index over
non-null values, or document and implement an equivalent deduplication table.
Do not expose raw database errors as the public service error.

## State and error rules

- Blank or whitespace-only title/description is rejected before a transaction.
- A duplicate idempotency key with an equivalent command returns the original
  result; reuse with materially different content raises a conflict.
- Plan creation is allowed once for an unplanned project, or is explicitly
  versioned; it must never silently append duplicate tasks.
- Transition attempts that skip required states or mutate a terminal task
  raise a typed domain error.
- A failed transaction leaves no order, project, conversation, event, or task
  half-created.
- Event publication failure must have a documented policy. For this issue,
  commit the database transaction first and surface/log publication failure;
  Issue #014 may replace this with an outbox.

## Tests and acceptance criteria

Add isolated, network-free tests for:

1. valid intake creates exactly one order, project, conversation, and intake
   event with linked IDs;
2. validation rejects blank fields and invalid budgets;
3. retrying an identical idempotency key is idempotent, while conflicting
   reuse is rejected;
4. plan creation persists deterministic task order and rejects invalid plans;
5. legal task transitions succeed and illegal/terminal transitions fail;
6. a transaction failure rolls back every related record;
7. state survives repository/database recreation and migration upgrade;
8. service code can run against fakes implementing repository/event protocols,
   proving it does not require SQLAlchemy or an interface adapter;
9. published events contain IDs and statuses but no private message body or
   credentials.

The implementation is complete when `uv run pytest`, `uv run ruff check .`,
and `uv run ruff format --check .` pass, the migration upgrades and downgrades,
and the new public classes/functions have short docstrings and type hints.

## Documentation and handoff

Update `docs/ARCHITECTURE.md` with the service-layer dependency direction,
task persistence, and the transaction/event policy. Update `README.md` only
for user-visible current capabilities and local migration/test commands. Add
no provider or Telegram configuration beyond placeholders already present.

## Risks and follow-up decisions

- Task dependencies may outgrow a JSON list; Issue #008 should decide whether
  to normalize edges before introducing parallel execution.
- Generic repositories currently expose broad CRUD; later services should
  narrow protocols and enforce aggregate ownership rather than adding more
  unrestricted updates.
- SQLite is sufficient for this issue. PostgreSQL, background workers, and an
  outbox belong to Issue #014, not this foundational vertical slice.
