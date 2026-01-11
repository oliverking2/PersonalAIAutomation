# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## How Claude Should Help

Beyond writing code, Claude should act as a thoughtful collaborator:

- **Challenge assumptions**: Point out potential issues before they become problems. Ask "have you considered X?" when there are better approaches.
- **Present options with trade-offs**: When multiple paths exist, lay them out with clear pros/cons rather than picking one silently.
- **Be direct about bad ideas**: If something is a bad idea, say so and explain why. Don't sugarcoat or go along with poor decisions to be agreeable.
- **Be realistic about complexity**: Don't oversell or undersell difficulty. Be honest about what's straightforward vs what will be tricky.
- **Explain the "why"**: Don't just implement - explain why we're choosing one approach over another.
- **Teach, don't just deliver**: Help understand what code is doing so it can be modified later. The goal is knowledge transfer, not just working code.

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
poetry run python -m unittest testing/path/to/test_file.py

# Run single test method
poetry run python -m unittest testing.path.to.test_file.TestClass.test_method

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
2. **Newsletter Parsing**: `src/newsletters/` extracts articles from HTML
3. **Storage**: `src/database/` persists to PostgreSQL via SQLAlchemy
4. **Alerting**: `src/alerts/` sends formatted messages via configured providers
5. **Orchestration**: `src/dagster/` schedules jobs via Dagster
6. **API**: `src/api/` exposes FastAPI endpoints
7. **Agent**: `src/agent/` provides AI-powered tool calling via AWS Bedrock

### Module Responsibilities

| Module               | Purpose                                        |
|----------------------|------------------------------------------------|
| `src/agent/`         | AI agent runtime with Bedrock tool calling     |
| `src/alerts/`        | Alert service with pluggable providers         |
| `src/api/`           | FastAPI REST endpoints with HTTPBearer auth    |
| `src/dagster/`       | Dagster jobs, ops, schedules, and resources    |
| `src/database/`      | SQLAlchemy models and database operations      |
| `src/graph/`         | Microsoft Graph API client for email access    |
| `src/newsletters/`   | Email parsing and article extraction           |
| `src/notion/`        | Notion API client, models, and parsing logic   |
| `src/observability/` | Sentry/GlitchTip error tracking integration    |
| `src/telegram/`      | Telegram Bot API client, polling, and chat     |
| `src/utils/`         | Shared utilities (logging configuration)       |

### Key Patterns

- **Domain logic in domain modules**: `src/notion/`, `src/telegram/`, etc. contain all business logic, models, clients, and parsing
- **Consumer layers are thin wrappers**: `src/api/`, `src/agent/`, `src/dagster/` orchestrate domain modules without duplicating logic
- **Database operations in dedicated files**: Functions in `src/database/*/operations.py`, not scattered across services
- **Pydantic models for boundaries**: Used for API schemas, parsed data, and configuration
- **SQLAlchemy models for persistence**: ORM in `src/database/*/models.py`

### Separation of Concerns

**Domain logic belongs in domain modules, not in consumers.**

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
└── tasks.py          # Tool definitions using CRUD factory
```

#### Rules for Consumer Layers

1. **Never duplicate domain logic**: If logic exists in a domain module, import and use it
2. **Reuse models**: Prefer importing models from domain modules over creating duplicates
3. **Keep wrappers thin**: Consumer code should only handle:
   - Input/output transformation specific to that interface (HTTP, tool spec, etc.)
   - Orchestration of domain operations
   - Interface-specific error handling

### Agent Tools Pattern

Agent tools call API endpoints via HTTP, not domain clients directly:

```
User Request → Agent → Tool Handler → HTTP → API Endpoint → Domain Logic
```

Tools use `InternalAPIClient` from `src/api/client.py`:

```python
# Good: Thin wrapper calling the API via CRUD factory
from src.api.client import InternalAPIClient

with InternalAPIClient() as client:
    response = client.post("/notion/tasks/query", json=args.model_dump())
```

This ensures:
- **Single source of truth**: All validation and business logic lives in the API
- **No duplication**: Models, validation, and error handling defined once
- **Consistent behaviour**: Agent and external clients use the same code path

## Project Structure

- Source code lives under `src/`. Place new code in the correct existing package/module.
- Tests live under `testing/` and mirror `src/` structure.
- Do not create new top-level folders unless explicitly asked.
- Review `ROADMAP.md` before starting work and update it when completing features.
- Review existing PRDs in `prds/` before implementing new features.

## Coding Standards

Detailed coding standards are in `.claude/rules/`:

### Core Standards
- **Python Style**: `.claude/rules/python-style.md` - Types, formatting, naming, docstrings
- **Testing**: `.claude/rules/testing.md` - unittest patterns, fixtures, coverage
- **Change Discipline**: `.claude/rules/change-discipline.md` - How to approach changes

### Architecture
- **Module Structure**: `.claude/rules/module-structure.md` - File organisation patterns
- **API Patterns**: `.claude/rules/api-patterns.md` - FastAPI endpoints, models, auth
- **Database**: `.claude/rules/database.md` - SQLAlchemy models, operations, migrations

### External Services
- **HTTP Clients**: `.claude/rules/http-clients.md` - Retries, timeouts, connection pooling
- **AWS Patterns**: `.claude/rules/aws-patterns.md` - boto3, Bedrock, S3, SSM
- **Caching**: `.claude/rules/caching.md` - lru_cache, TTL, invalidation

### Quality & Safety
- **Error Handling & Logging**: `.claude/rules/error-handling.md` - Exceptions, logging
- **Observability**: `.claude/rules/observability.md` - Sentry, structured logging, metrics
- **Security**: `.claude/rules/security.md` - Input validation, auth, OWASP
- **Data Validation**: `.claude/rules/data-validation.md` - Pydantic, sanitisation
- **Configuration**: `.claude/rules/configuration.md` - Environment variables, secrets

## Validation Requirements

All changes must pass before considering work complete:

```bash
make check  # Runs lint, format, types, coverage
```

- All changes must pass `ruff check` and `ruff format --check`
- All changes must pass `mypy` with no errors
- All changes must pass tests with at least 80% coverage
- Update `README.md` to reflect new or modified behaviour
- Update `ROADMAP.md` to reflect completed features
