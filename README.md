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
