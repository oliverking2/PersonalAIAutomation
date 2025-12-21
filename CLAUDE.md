# Project Rules

## Core Principles
- Optimise for clarity, maintainability, and consistency with existing project patterns.
- Preserve existing public APIs and behaviours unless explicitly instructed otherwise.
- Prefer small, testable units. Avoid cleverness.

## Python & Tooling Baseline
- Target Python 3.12 and above.
- Use type annotations everywhere (public and internal). Avoid `Any` unless there is a clear, documented reason.
- Mypy strictness: aim for "as close to strict as the project permits". Do not silence errors with broad ignores.
- Dependency management must use Poetry only:
  - If a dependency is required, mention `poetry add <package>` (and nothing else).
- Do not introduce alternative env managers or install flows (pip, conda, uv, etc).

## Project Structure
- Source code lives under `src/`. Place new code in the correct existing package/module, following current patterns.
- Tests live under `testing/` and mirror `src/` structure.
- Do not create new top-level folders unless explicitly asked.

## Coding Style
- Ruff compatible formatting. Follow settings in `pyproject.toml`.
- British English spelling in comments, docstrings, user-facing text, and error messages.
- Prefer small, composable functions (aim: <50 lines, low branching).
- Avoid deeply nested logic. Use guard clauses and helper functions.
- Never use bare `except:`. Catch specific exceptions.
- Raise exceptions with clear messages that explain:
  - what failed
  - the relevant identifier(s)
  - the expected shape/state

## Logging
- Use the standard library `logging` module.
- Use module-level loggers: `logger = logging.getLogger(__name__)`.
- Log actionable context (ids, counts, timings) but never secrets or personal data.
- Prefer structured-ish logging via consistent key/value wording even if using plain logging.
- Do not `print()` in production code.

## Pydantic
- Use Pydantic models for data validation and boundaries (API schemas, configs where applicable).
- Keep models typed precisely (avoid `dict[str, object]` when a model or `TypedDict` is clearer).
- Prefer explicit field constraints and meaningful names over ad-hoc validation sprinkled in handlers.

## Imports & Naming
- Use absolute imports within `src` unless the project clearly prefers relative imports.
- Keep naming explicit and domain-aligned; avoid vague verbs like `handle`, `do`, `process` without context.
- Constants: `UPPER_SNAKE_CASE`. Public API should be stable and documented.

## Docstrings & Documentation
- Public functions/classes must include Sphinx-style docstrings using `:param:`, `:raises:`, `:returns:`.
- If you add or change user-facing behaviour, update the relevant README/docs snippet.

## Environment Configuration
- Use `.env` for local development (never commit).
- Document all required variables in `.env_example`.
- Access via `python-dotenv` and `os.environ`.

## Data & I/O Safety
- Never hard-code secrets. Use environment variables or existing configuration patterns.
- Do not log credentials, tokens, or full payloads containing personal data.
- Prefer `pathlib.Path` over `os.path`.
- When interacting with external systems (HTTP, DB, S3, APIs):
  - use timeouts
  - handle retryable errors explicitly where appropriate
  - ensure failures are actionable (good error messages)

## AWS (boto3)
- Use typed stubs from `boto3-stubs`.
- Always use explicit resource/client types.
- Handle AWS exceptions specifically (e.g., `botocore.exceptions.ClientError`).

## Testing (unittest)
- All new behaviour must include `unittest` tests under `testing/`.
- Tests should cover:
  - the happy path
  - at least one edge case
  - at least one failure mode (if applicable)
- Keep tests readable and deterministic. Avoid network calls unless the project already uses integration tests/mocking patterns.
- Aim for at least 80% test coverage.
- Leverage `setUp`/`setUpClass` and `tearDown`/`tearDownClass` to avoid boilerplate.

## Static Analysis (mypy)
- Generated code must pass mypy according to the project's configured strictness.
- Prefer precise types over broad ones (use `TypedDict`, `Protocol`, `Literal`, `NewType` where helpful).
- Avoid `# type: ignore` unless it is narrowly scoped and justified with a reason comment.
- Add type stubs for third-party libraries where possible. Add them to the poetry `checks` group.

## Project-Specific Prohibitions

## Change Discipline
- Before writing new code, look for an existing pattern and match it.
- If a change could be breaking, propose a non-breaking alternative first.
- When uncertain about an existing convention, ask a targeted question instead of guessing.

## Validation Requirements
- All changes must pass `ruff check` and `ruff format --check`.
- All changes must pass `mypy` with no errors.
- All changes must pass tests in the `testing/` folder with at least 80% coverage.
- For all changes, update the `README.md` to reflect new or modified behaviour.

## Validation Commands
- Lint: `poetry run ruff check --fix`
- Format: `poetry run ruff format`
- Types: `poetry run mypy .`
- Tests with coverage: `poetry run coverage run -m unittest discover testing/ && poetry run coverage report --fail-under=80`

## Git
- Write clear, imperative commit messages.
- Keep commits atomic and focused.
- Pre-commit hooks run automatically on commit.

## Self-Check Before Final Output
- Confirm imports are correct and minimal.
- Confirm types line up (no obvious mypy failures).
- Confirm tests match the behaviour and run in isolation.
- Confirm no secrets, tokens, or private data are introduced.
- Run `ruff check`, `mypy`, and coverage tests before considering work complete.