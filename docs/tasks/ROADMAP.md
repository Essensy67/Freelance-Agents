# Commercial platform roadmap

This roadmap starts after Issue #005. The repository currently has an
asynchronous Python foundation, configuration and lifecycle handling, and
generic SQLite persistence for orders, projects, conversations, messages,
employees, and project events. It does not yet have application services,
task records, model-provider calls, a worker loop, approval workflows, or a
client interface.

## MVP outcome

The first usable product is a single-tenant, operator-managed agency that can
accept one client order, turn it into a plan, run a small configured set of AI
agents, retain the complete audit trail and cost, and expose a human approval
gate before delivery. Telegram is the first interface because the settings
and project identity already reserve it; a web adapter can follow without
changing the use cases.

The MVP deliberately excludes marketplace discovery, autonomous payment,
multi-tenant billing, arbitrary tool use, scheduling, and a large agent
marketplace. Every external boundary is an interface and has a deterministic
fake for offline tests.

## Numbered issues

### Issue #006 — Order intake and workflow foundation

Create the first application-service vertical slice: accept and validate a
client order, create its project and conversation, and represent the ordered
work as durable tasks with explicit lifecycle states. Define the service
ports, domain value objects, event names, idempotency rule, and transaction
boundary that later analysis, execution, approval, and interface adapters will
use. Detailed specification: [006-order-intake-and-workflow-foundation.md](006-order-intake-and-workflow-foundation.md).

### Issue #007 — AI provider port, first adapter, and usage accounting

Define a provider-neutral async completion interface and normalized request,
response, error, and usage types. Add one OpenAI-compatible HTTP adapter
behind that port, configuration validation, timeout/retry policy, redacted
logging, and a cost calculator. Persist each call with model, token usage,
latency, status, and estimated cost; use a fake provider in tests. No business
workflow should import a concrete SDK.

### Issue #008 — Order analysis and task decomposition

Add an analysis service that reads an accepted order, sends a bounded,
structured prompt through the provider port, validates the returned plan, and
creates an ordered task graph. Persist the analysis conversation and raw
provider output as private audit data, with a safe normalized plan for the
workflow. Invalid, incomplete, or duplicate plans fail closed and leave a
retryable status rather than creating partial work.

### Issue #009 — Agent catalog and deterministic assignment

Turn the existing employee records into configured AI-agent profiles with a
capability set, model policy, concurrency limit, and active status. Implement
an assignment service that matches task requirements to available agents,
records the decision and assignment version, and handles no-match and busy
cases explicitly. Keep assignment deterministic and human-overridable.

### Issue #010 — Task execution and orchestration

Implement the application worker/use case that executes ready tasks in
dependency order through the provider port, stores prompts, outputs, usage,
costs, attempts, and errors, and updates task/project statuses transactionally.
Start with an in-process runner callable from the interface; add a durable
queue or background worker only when the state machine and retries are proven.

### Issue #011 — Human review, approval, and delivery gate

Add a review aggregate and service for approve, reject-with-feedback, and
request-revision actions. A project cannot be delivered unless every required
task is complete and an authorized human approval exists for the exact output
version. Persist reviewer, decision, timestamp, feedback, and immutable output
revision; make approval idempotent and auditable.

### Issue #012 — Telegram MVP interface

Add a thin Telegram adapter that maps commands/messages to application
services: submit an order, view status, inspect a plan, approve/reject a
deliverable, and receive the final delivery. It must not contain business
logic or access repositories directly. Add webhook/polling configuration,
secret-safe error handling, user-to-project association, and adapter tests
with a fake transport. This is the first shippable client interface.

### Issue #013 — Operator web interface (post-MVP alternative)

Expose the same use cases through a minimal authenticated HTTP UI/API for
operators and clients who do not use Telegram. Reuse service DTOs and approval
rules; do not duplicate orchestration in request handlers. Keep this issue
optional for the initial launch.

### Issue #014 — Reliability, resumability, and operational controls

Replace the in-process trigger with a durable job/outbox mechanism, lease and
retry handling, dead-letter visibility, restart recovery, idempotency keys,
and bounded concurrency. Add health/readiness checks, structured metrics and
traces, and dashboards for task failures, latency, approval backlog, and spend.

### Issue #015 — Security, privacy, and tenancy baseline

Add authenticated users and roles, tenant/project isolation, encrypted secret
configuration, retention/deletion controls, provider-data policy, prompt and
output redaction, and audit access controls. Threat-model Telegram identity,
web sessions, prompt injection, malicious files, and cross-project leakage.

### Issue #016 — Commercial operations

Add quotes, budgets, spend limits, per-order margin estimates, provider cost
and price records, invoices/payment integration boundaries, and operator
alerts. Enforce budget ceilings before provider calls and make all monetary
calculations reproducible.

### Issue #017 — Quality and agent evaluation

Create task-type acceptance criteria, golden datasets, regression evaluations,
human feedback capture, output validators, and release gates for prompts,
models, and agent configurations. Track quality alongside cost and latency.

### Issue #018 — Scale and integrations

Only after the core workflow is reliable, add multiple provider adapters,
files and tool sandboxes, parallel execution, marketplace/order imports,
additional interfaces, and production deployment automation. Each integration
must preserve the provider, service, and domain boundaries established in
Issues #006–#017.

## Dependency and release order

The minimum critical path is `006 → 007 → 008 → 009 → 010 → 011 → 012`.
Issue #006 can be implemented and tested without network access. Issue #007
can land independently but is required before real analysis or execution.
Issues #013–#018 are deliberately outside the smallest usable release.

## MVP acceptance scenario

An operator submits an order in Telegram, receives a persisted order and
project, starts analysis, reviews the generated task plan, sees tasks assigned
to configured agents, and starts execution. The system records every
conversation, provider call, output, status transition, and estimated cost.
The operator rejects or approves the exact final output; only approval permits
the bot to deliver it to the client. Restarting the application does not lose
state, and a provider failure is visible and retryable without duplicating
tasks or charges.
