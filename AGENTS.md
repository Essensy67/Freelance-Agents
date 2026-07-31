# Freelance Agents — AI Development Guidelines

This file is the primary development instruction for all AI developers working
on the project, including Codex and Claude Code.

## 1. Project identity

**Name:** Freelance Agents

Freelance Agents is not merely a Telegram bot; it is a virtual freelance
company. Telegram is only one possible interface. A website, dashboard, and
other interfaces may be added in the future.

## 2. Architecture principles

The system is organized around these layers:

- `core` — independent domain logic;
- `services` — application operations and integrations;
- `app` — entry points and interfaces;
- `database` — the future persistence layer;
- `tests` — automated tests;
- `docs` — documentation and technical decisions.

The following rules apply:

- `core` must not import Telegram, a database, or a concrete AI SDK.
- Employees must not work directly with Telegram, SQLite, or external APIs.
- Business logic belongs in services.
- Employees primarily coordinate services.
- Dependencies are assembled in `Application`.
- Components should communicate through events where practical.
- Do not use global mutable state.
- Do not create circular imports.
- Do not over-engineer the system prematurely.

## 3. Technology rules

- Python 3.13+;
- `src` layout;
- async-first when an operation is genuinely asynchronous;
- type hints are required;
- short docstrings are required for public classes, functions, and methods;
- dataclasses are acceptable for simple domain models;
- use UUIDs for domain entity identifiers;
- store time in UTC;
- use Ruff for linting and formatting;
- use pytest and pytest-asyncio for tests;
- manage dependencies with uv.

## 4. Testing rules

For every new feature:

- add or update tests;
- cover the normal scenario;
- cover important errors and edge cases;
- keep tests independent of the network;
- keep tests independent of execution order;
- do not use `sleep` without a necessity.

Required checks are:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 5. Git rules

Without the user's direct permission, an AI developer must not:

- run `git commit`;
- run `git push`;
- change a Git remote;
- rewrite Git history;
- delete branches;
- use force push.

Reading `git status`, `git diff`, and `git log` is allowed.

## 6. Security rules

Do not:

- add API keys, tokens, or passwords to the repository;
- print secrets to the console or tests;
- change files outside the repository;
- upload user data to external services without permission;
- add real secrets to `.env.example`.

Future secrets must be loaded from environment variables.

## 7. Change workflow

Every feature follows this sequence:

**Architecture discussion → Specification → Implementation → Tests → Review →
Commit**

Before implementing a substantial module, there must be a task in `docs/tasks`
or a specification in `docs/specs`.

## 8. Scope control

An AI developer must:

- perform only the assigned task;
- not add “future” features without a request;
- not change the architecture without a separate decision;
- not perform a large refactor inside a small task;
- preserve backward compatibility unless instructed otherwise;
- report discovered problems, but not fix unrelated problems without permission.

## 9. Definition of Done

A task is complete only when:

- its requirements are met;
- tests were added or their absence is justified;
- pytest passes;
- Ruff passes;
- documentation is updated;
- no secrets are present;
- Codex reports the list of changed files;
- Codex reports known limitations.

## 10. Current project boundaries

The following are not implemented at the current stage:

- Telegram;
- a database;
- AI providers;
- freelance-order search;
- real employees;
- memory;
- a scheduler;
- a web dashboard.

Do not add any of these as part of Issue #002.
