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
Logging outputs to both stdout and a file. Configure via environment variables:
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `LOG_FILE`: Log file path. Relative paths use project root (default: app.log)

#### Database
PostgreSQL database for storing newsletters and articles:
- `DATABASE_HOST`: Database host (default: localhost)
- `DATABASE_PORT`: Database port (default: 5432)
- `DATABASE_NAME`: Database name
- `DATABASE_USER`: Database user
- `DATABASE_PASSWORD`: Database password

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

Supported newsletters:
- TLDR (general tech news)
- TLDR AI (AI/ML focused)
- TLDR Dev (developer focused)

### Telegram Alerts
Sends newsletter summaries to Telegram with article titles and links. Newsletters are tracked to prevent duplicate alerts.

### Scheduled Processing
Newsletter processing and alerting runs automatically using Celery with Redis as the message broker.

#### Configuration
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379/0)
- `REDIS_PORT`: Redis port for Docker (default: 6379)
- `FLOWER_PORT`: Flower monitoring UI port (default: 5555)

#### Running with Docker
Start all services including the scheduler:
```bash
docker-compose up -d
```

This starts:
- PostgreSQL database
- Redis message broker
- Celery worker (processes tasks)
- Celery beat (schedules hourly tasks)
- Flower (monitoring at http://localhost:5555)

#### Running Locally
Start Redis (via Docker or locally), then run:
```bash
# Start the worker
poetry run celery -A src.orchestration.celery_app worker --loglevel=info

# In another terminal, start the scheduler
poetry run celery -A src.orchestration.celery_app beat --loglevel=info

# Optional: Start Flower for monitoring
poetry run celery -A src.orchestration.celery_app flower --port=5555
```

#### Manual Task Execution
Trigger tasks manually via Python:
```python
from src.orchestration.tasks import process_newsletters_task, send_alerts_task

# Process newsletters from the last day
process_newsletters_task.delay()

# Send pending Telegram alerts
send_alerts_task.delay()
```
