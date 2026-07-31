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

The application starts the company, prints a confirmation, and exits without
running a background loop.

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
└── core/
    ├── company.py       # company aggregate
    ├── employees/       # employee model and status
    └── events/          # event model and asynchronous event bus
tests/                   # unit tests
docs/tasks/              # task scope and acceptance criteria
```
