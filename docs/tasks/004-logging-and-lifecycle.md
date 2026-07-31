# Issue #004 — Logging and application lifecycle

## Goal

Add predictable application logging and guarantee orderly startup and shutdown
for the current one-shot MVP, including interruption by `SIGINT` and `SIGTERM`.

## Architecture

- Logging configuration is application infrastructure and remains outside
  `core`.
- `Application` owns the company lifecycle and uses its injected `Settings`.
- The CLI owns operating-system signal registration and delegates lifecycle
  work to `Application`.
- No logging configuration or application instance is created at import time.

## Lifecycle behavior

- `Application.run()` configures logging from `Settings.log_level`, logs a safe
  settings summary, and starts the company.
- `Application.shutdown()` is always called from `run()` through `finally`, on
  successful startup, startup failure, cancellation, or interruption.
- Shutdown remains idempotent through the existing `Company.stop()` behavior.
- The CLI registers `SIGINT` and `SIGTERM` handlers when the event loop supports
  them. A received signal cancels the active lifecycle task so its `finally`
  block performs shutdown.
- Signal handlers are removed when the CLI lifecycle finishes.

## Logging and secrets

- The configured root log level comes from `Settings.log_level`.
- Startup diagnostics use only `Settings.safe_summary()`.
- Telegram tokens and AI API keys are never passed to log records.
- Startup and shutdown failures are logged and propagated to the caller.

## Definition of done

- Normal startup is logged and followed by shutdown.
- Startup and shutdown errors are logged and remain visible to callers.
- Cancellation still invokes shutdown.
- `SIGINT` and `SIGTERM` request orderly termination.
- Tests prove that configured secrets do not appear in captured log output.
- pytest, Ruff, both entry points, and Git whitespace checks pass.

## Deliberately out of scope

- Long-running workers or a scheduler.
- Telegram, database, AI provider, or marketplace integrations.
- Structured logging services, log shipping, tracing, or metrics.
- New business logic or changes to domain dependency direction.
