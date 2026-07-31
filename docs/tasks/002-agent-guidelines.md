# Issue #002 — Development Rules and Architecture Documentation

## Goal

Define the common rules for AI developers and record the project's baseline
architecture without changing the application implementation.

## Created documents

- `AGENTS.md` — primary instructions for Codex, Claude Code, and other AI
  developers;
- `docs/ARCHITECTURE.md` — current components, dependency direction, runtime
  behavior, and future boundaries;
- `docs/tasks/002-agent-guidelines.md` — scope and acceptance record for this
  issue.

## Completion criteria

- all requested development, testing, Git, security, scope, and completion
  rules are documented in `AGENTS.md`;
- current and future architecture boundaries are documented accurately;
- `uv run pytest` passes;
- `uv run ruff check .` passes;
- `uv run ruff format --check .` passes;
- source code and tests are unchanged.

## Scope note

Issue #002 changes documentation only. The application source under `src/` and
the tests under `tests/` were not modified. No Telegram, database, AI provider,
marketplace search, employee implementation, memory, scheduler, or dashboard
was added.
