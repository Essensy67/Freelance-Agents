# Freelance Agents

Freelance Agents is an asynchronous Python foundation for a virtual company of
specialized agents. The project is currently at the foundation stage of its MVP:
it provides lifecycle models for a company and its employees plus a small
in-process event bus.

Issue #001 intentionally contains no freelance marketplace integrations,
Telegram bot, AI agents, or database layer.

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

The current one-shot MVP logs its safe startup configuration, starts the
company, and always shuts it down before exiting. During the lifecycle,
`SIGINT` and `SIGTERM` request orderly cancellation and cleanup.

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
├── config/              # environment-backed infrastructure settings
├── logging_config.py    # standard logging setup
└── core/
    ├── company.py       # company aggregate
    ├── employees/       # employee model and status
    └── events/          # event model and asynchronous event bus
tests/                   # unit tests
docs/tasks/              # task scope and acceptance criteria
```
