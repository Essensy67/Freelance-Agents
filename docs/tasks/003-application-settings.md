# Issue #003 — Application settings

## Goal

Provide one type-safe infrastructure configuration module that reads
`FA_`-prefixed environment variables and an optional `.env` file while keeping
the domain layer independent from configuration concerns.

## Implemented components

- `Environment` and `LogLevel` string enums for validated runtime values.
- `Settings` based on `pydantic-settings`, with MVP-safe defaults.
- `load_settings` factory that creates uncached, independent settings objects.
- Safe configuration summaries that report whether secrets are configured
  without exposing their values.
- Dependency injection of `Settings` into the `Application` composition root.
- A safe `.env.example` and documented configuration workflow.

## Environment variables

- `FA_APP_NAME`
- `FA_ENVIRONMENT`
- `FA_DEBUG`
- `FA_LOG_LEVEL`
- `FA_DATABASE_URL`
- `FA_TELEGRAM_BOT_TOKEN`
- `FA_AI_API_KEY`
- `FA_AI_BASE_URL`
- `FA_AI_MODEL`

Variable names are case-insensitive where the operating system supports that
behavior. Direct constructor arguments take precedence and support tests and
dependency injection.

## Secret handling

Telegram tokens and AI API keys use Pydantic `SecretStr`. They must never be
committed, logged, included in summaries, or placed in error messages.
`.env.example` contains empty placeholders only; real values belong in the
ignored local `.env` file or the process environment.

## Definition of done

- Defaults run the current MVP without credentials.
- Environment variables, direct overrides, booleans, and enums are validated.
- No settings object is created during module import or cached globally.
- `Application` accepts injected settings and uses the configured company name.
- Tests isolate both the process environment and any local `.env` file.
- pytest, Ruff, both application entry points, and Git whitespace checks pass.

## Deliberately out of scope

- Connecting to Telegram, a database, or an AI provider.
- Validating credentials against external services.
- Business logic or employee implementations.
- Persistence, memory, scheduling, marketplace search, or web interfaces.
