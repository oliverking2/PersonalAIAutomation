# Personal AI Automation

## Project Goal
This project is a personal, cloud-hosted AI assistant designed to automate day-to-day information workflows through a single conversational interface.

The assistant is accessed via a private 1:1 Telegram chat, where it can both proactively send notifications and respond interactively to questions and follow-up requests. It is intended to act as a persistent, context-aware assistant rather than a stateless chatbot.

The primary use cases include:
- summarising blog posts and articles received via email
- scraping and summarising daily content such as Medium digests
- answering questions and performing small automated tasks via natural language reducing manual overhead in recurring personal workflows

The system maintains conversational context across sessions using persisted history and summaries, allowing it to build continuity over time.

## Setup

### Prerequisites
- Python 3.12+
- Poetry

### Installation
```bash
poetry install
```

### Configuration
Copy `.env_example` to `.env` and populate the required values.

#### Logging
Logging outputs to stdout. Configure via environment variables:
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `LOG_UVICORN_ACCESS`: Enable uvicorn access logs (default: false)

#### Database
PostgreSQL database for storing newsletters and articles.

For local development:
- `DATABASE_HOST`: Database host (default: localhost)
- `DATABASE_PORT`: Database port (default: 5432)

For Docker (used by init script to create databases/users):
- `POSTGRES_USER`: PostgreSQL superuser
- `POSTGRES_PASSWORD`: PostgreSQL superuser password
- `APP_DB_PASSWORD`: Password for `app` user (main application)
- `DAGSTER_DB_PASSWORD`: Password for `dagster` user (orchestration)
- `GLITCHTIP_DB_PASSWORD`: Password for `glitchtip` user (error tracking)

#### Telegram
Send newsletter alerts via Telegram bot:
- `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather
- `TELEGRAM_CHAT_ID`: Target chat ID for messages

Start the database with Docker:
```bash
docker-compose up -d
```

Run migrations:
```bash
poetry run alembic upgrade head
```

## Features

### Newsletter Extraction
Fetches TLDR newsletters (standard, AI, Dev) from Outlook via Microsoft Graph API, extracts articles, and stores them in PostgreSQL.

Uses watermark-based incremental extraction to track the last processed timestamp, ensuring only new newsletters are fetched on each run. The watermark can be overridden via Dagster job configuration for backfills.

Supported newsletters:
- TLDR (general tech news)
- TLDR AI (AI/ML focused)
- TLDR Dev (developer focused)

### Telegram Alerts
Sends newsletter summaries to Telegram with article titles and links. Newsletters are tracked to prevent duplicate alerts.

### Scheduled Processing
Newsletter processing and alerting runs automatically using Dagster for orchestration.

#### Configuration
- `DAGSTER_WEBSERVER_PORT`: Dagster webserver UI port (default: 3000)

#### Running with Docker
Start all services including the scheduler:
```bash
docker-compose up -d
```

This starts:
- PostgreSQL database with three databases and users:
  - `personal_ai_automation` (user: `app`) - main application data
  - `dagster` (user: `dagster`) - orchestration storage
  - `glitchtip` (user: `glitchtip`) - error tracking
- Dagster webserver (UI at http://localhost:3000)
- Dagster daemon (runs schedules)
- FastAPI (API at http://localhost:8000)
- GlitchTip (error tracking at http://localhost:8001)

#### Running Locally
Run Dagster dev server for local development:
```bash
poetry run dagster dev
```

This uses SQLite storage and doesn't require PostgreSQL.

#### Manual Job Execution
Trigger jobs manually via the Dagster UI at http://localhost:3000 or via Python:

```python
from src.dagster.newsletters.jobs import newsletter_pipeline_job

# Execute the job
newsletter_pipeline_job.execute_in_process()
```

### REST API
FastAPI REST API for health checks and future endpoints.

#### Configuration
- `API_AUTH_TOKEN`: Bearer token for API authentication
- `API_PORT`: API server port (default: 8000)

#### Running with Docker
The API service starts automatically with docker-compose. Access OpenAPI documentation at http://localhost:8000/docs.

#### Running Locally
```bash
poetry run uvicorn src.api.app:app --reload
```

#### Endpoints
| Method   | Path    | Auth | Description  |
|----------|---------|------|--------------|
| GET      | /health | No   | Health check |
