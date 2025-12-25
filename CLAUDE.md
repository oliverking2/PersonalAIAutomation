# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```bash
# Install dependencies
make install

# Run all validation (lint, format, types, coverage)
make check

# Individual validation commands
make lint      # Ruff linting with fixes
make format    # Ruff formatter
make types     # mypy type checking
make test      # Unit tests only
make coverage  # Tests with coverage (80% threshold)

# Run single test file
poetry run python -m unittest testing/api/test_health.py

# Run single test method
poetry run python -m unittest testing.api.test_health.TestHealthEndpoint.test_health_check_returns_200

# Database migrations
poetry run alembic upgrade head
poetry run alembic revision --autogenerate -m "description"

# Start services locally
docker-compose up -d                         # All services
poetry run dagster dev                       # Dagster dev server
poetry run uvicorn src.api.app:app --reload  # API only

# Clean build artefacts
make clean
```

## Architecture

### Data Flow
1. **Email Ingestion**: `src/graph/` fetches emails via Microsoft Graph API
2. **Newsletter Parsing**: `src/newsletters/tldr/` extracts articles from HTML
3. **Storage**: `src/database/newsletters/` persists to PostgreSQL via SQLAlchemy
4. **Alerting**: `src/telegram/` sends formatted messages to Telegram
5. **Orchestration**: `src/dagster/` schedules jobs via Dagster
6. **API**: `src/api/` exposes FastAPI endpoints

### Key Patterns
- **Service layer**: Business logic in `*Service` classes (e.g., `NewsletterService`, `TelegramService`)
- **Database operations**: Functions in `src/database/*/operations.py`, not in services
- **Pydantic models**: Used for API schemas and parsed data (not ORM)
- **SQLAlchemy models**: ORM in `src/database/*/models.py`
- **Dependency injection**: Services take `Session` and clients as constructor args

### Module Responsibilities
| Module               | Purpose                                        |
|----------------------|------------------------------------------------|
| `src/agent/`         | AI agent runtime with Bedrock tool calling     |
| `src/api/`           | FastAPI REST endpoints with HTTPBearer auth    |
| `src/dagster/`       | Dagster jobs, ops, schedules, and resources    |
| `src/database/`      | SQLAlchemy models and database operations      |
| `src/graph/`         | Microsoft Graph API client for email access    |
| `src/newsletters/`   | Email parsing and article extraction           |
| `src/notion/`        | Notion API client, models, and parsing logic   |
| `src/observability/` | Sentry/GlitchTip error tracking integration    |
| `src/telegram/`      | Telegram Bot API client and alerting           |

### Separation of Concerns

**Domain logic belongs in domain modules, not in consumers.**

The project follows a strict separation where:
- **Domain modules** (`src/notion/`, `src/telegram/`, etc.) contain all business logic, models, clients, and parsing
- **Consumer layers** (`src/api/`, `src/agent/`, `src/dagster/`) are thin wrappers that orchestrate domain modules

#### Example: Notion Integration

```
src/notion/           <- Domain logic lives here
├── client.py         # NotionClient with all API operations
├── models.py         # NotionTask, NotionGoal, NotionReadingItem
├── parser.py         # build_task_properties(), parse_page_to_task()
└── enums.py          # Priority, TaskStatus, ReadingStatus, etc.

src/api/notion/       <- Thin HTTP wrapper
└── tasks/
    ├── endpoints.py  # HTTP handlers that call NotionClient
    └── models.py     # Request/response models (can reuse from src/notion/)

src/agent/tools/      <- Thin tool wrapper
└── tasks.py          # Tool handlers that call NotionClient
```

#### Rules for Consumer Layers

1. **Never duplicate domain logic**: If logic exists in a domain module, import and use it
2. **Reuse models**: Prefer importing models from domain modules over creating duplicates
3. **Keep wrappers thin**: Consumer code should only handle:
   - Input/output transformation specific to that interface (HTTP, tool spec, etc.)
   - Orchestration of domain operations
   - Interface-specific error handling
4. **Shared models**: If the same model is needed across API and Agent, place it in the domain module (`src/notion/models.py`) or create a shared location

#### Agent Tools Pattern

Agent tools in `src/agent/tools/` are thin HTTP wrappers that call the API:

```
User Request → Agent → Tool Handler → HTTP → API Endpoint → Domain Logic
```

Agent tools should:
- Call API endpoints via HTTP (localhost in development)
- Use a shared API client for authentication and base URL
- Only define tool-specific metadata (name, description, risk level)
- Return API responses directly (already serialised)

```python
# Good: Thin wrapper calling the API
from src.agent.api_client import AgentAPIClient


def create_reading_item(args: CreateReadingItemArgs) -> dict[str, Any]:
    client = AgentAPIClient()
    response = client.post("/notion/reading-list", json=args.model_dump())
    return response


# Bad: Calling domain clients directly (duplicates API logic)
def create_reading_item(args: CreateReadingItemArgs) -> dict[str, Any]:
    # DON'T: Call NotionClient directly - use the API instead
    client = NotionClient()
    properties = build_reading_properties(...)
```

This pattern ensures:
- **Single source of truth**: All validation and business logic lives in the API
- **No duplication**: Models, validation, and error handling defined once
- **Consistent behaviour**: Agent and external clients use the same code path
- **Easy testing**: Mock HTTP calls, not domain internals

## Project Rules

### Core Principles
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

### API File Structure
API endpoints follow a modular structure organised by resource:

```
src/api/<domain>/
├── __init__.py           # Exports router
├── router.py             # Combines sub-routers
├── dependencies.py       # FastAPI dependencies (shared across resources)
├── common/
│   ├── __init__.py
│   ├── models.py         # Shared response models
│   └── utils.py          # Shared utility functions
└── <resource>/           # One directory per resource (e.g., tasks, pages)
    ├── __init__.py
    ├── endpoints.py      # FastAPI route handlers
    └── models.py         # Request/response Pydantic models
```

Guidelines:
- **One resource per directory**: Keep endpoints, models, and logic for each resource together.
- **Separate concerns**: `endpoints.py` handles HTTP, `models.py` defines schemas.
- **Shared code in `common/`**: Put reusable models and utilities in the `common/` subdirectory.
- **Dependencies at domain level**: Place FastAPI dependencies (e.g., `get_notion_client`) in `dependencies.py`.
- **Avoid monolithic files**: Do not put all endpoints in a single `endpoints.py` file.

### Core Module File Structure
Core modules (non-API) follow a simpler structure:

```
src/<module>/
├── __init__.py           # Exports public API
├── client.py             # External API client (if applicable)
├── models.py             # Pydantic models for data
├── parser.py             # Data transformation functions
├── enums.py              # StrEnum definitions (if applicable)
└── exceptions.py         # Custom exceptions
```

### Agent Module Structure

The agent module provides AI-powered tool calling via AWS Bedrock:

```
src/agent/
├── __init__.py           # Exports public API
├── client.py             # BedrockClient for Converse API
├── models.py             # ToolDef, ToolMetadata, ToolSelectionResult
├── registry.py           # ToolRegistry for tool management
├── selector.py           # ToolSelector (AI-first with fallback)
├── enums.py              # RiskLevel enum
├── exceptions.py         # Agent-specific exceptions
└── tools/                # Tool handlers by domain
    ├── __init__.py
    └── reading_list.py   # Reading list tool wrappers
```

**Important**: Tool handlers in `src/agent/tools/` must be thin wrappers:
- Reuse argument models from domain modules where possible
- Call domain clients/parsers, never duplicate their logic
- Only add tool-specific concerns (ToolDef metadata, serialisation)

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

## Enums
- Use `StrEnum` for any parameter or field with a defined set of valid string values.
- Never use string literals where an enum exists (e.g., use `CallType.CHAT` not `"chat"`).
- Define enums in `enums.py` within the relevant module (e.g., `src/agent/enums.py`, `src/notion/enums.py`).
- StrEnum values automatically convert to strings for database storage and JSON serialisation.

## Logging
- Use the standard library `logging` module.
- Use module-level loggers: `logger = logging.getLogger(__name__)`.
- Use f-strings for all string formatting, including log messages.
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

## README Guidelines
- Keep documentation high-level and concise.
- Focus on what things do, not implementation details.
- Document configuration options (environment variables, settings).
- No code examples unless essential for usage.

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

### Avoid These Anti-Patterns
1. **Broad exception catches**: Never use bare `except:` or `except Exception:` without re-raising or specific handling. Catch specific exceptions to enable proper error recovery.
2. **Duplicating domain logic**: If logic exists in a domain module (`src/notion/`, `src/telegram/`, etc.), import and use it. Never duplicate validation, parsing, or business rules in API endpoints or agent tools.
3. **Missing timeouts**: All HTTP calls to external services (Notion, Telegram, Bedrock) must include explicit timeouts.
4. **Configuration in code**: Never hard-code configuration values. Use environment variables via `os.environ` with sensible defaults where appropriate.
5. **Inline type ignores without reason**: If `# type: ignore` is necessary, include a reason comment explaining why.

## Change Discipline
- Before writing new code, look for an existing pattern and match it.
- If a change could be breaking, propose a non-breaking alternative first.
- When uncertain about an existing convention, ask a targeted question instead of guessing.
- Consider the roadmap which is saved in `ROADMAP.md`
- Review existing PRDs in `.claude/prds/` before implementing new features

## Validation Requirements
- All changes must pass `ruff check` and `ruff format --check`.
- All changes must pass `mypy` with no errors.
- All changes must pass tests in the `testing/` folder with at least 80% coverage.
- For all changes, update the `README.md` to reflect new or modified behaviour.

## Validation Commands
- All checks: `make check`
- Lint: `make lint`
- Format: `make format`
- Types: `make types`
- Tests with coverage: `make coverage`

## Git
- Write clear, imperative commit messages.
- Keep commits atomic and focused.
- Pre-commit hooks run automatically on commit.

## Self-Check Before Final Output
- Confirm imports are correct and minimal.
- Confirm types line up (no obvious mypy failures).
- Confirm tests match the behaviour and run in isolation.
- Confirm no secrets, tokens, or private data are introduced.
- Run `make check` before considering work complete.
- Make sure `README.md` is up to date with any changes.
