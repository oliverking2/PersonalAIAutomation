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

##### Health
| Method | Path    | Auth | Description  |
|--------|---------|------|--------------|
| GET    | /health | No   | Health check |

##### Notion (Generic)
| Method | Path                                        | Auth  | Description                       |
|--------|---------------------------------------------|-------|-----------------------------------|
| GET    | /notion/databases/{database_id}             | Yes   | Retrieve database structure       |
| GET    | /notion/data-sources/{data_source_id}       | Yes   | Retrieve data source config       |
| POST   | /notion/data-sources/{data_source_id}/query | Yes   | Query all pages (auto-pagination) |
| GET    | /notion/data-sources/templates              | Yes   | List data source templates        |
| GET    | /notion/pages/{page_id}                     | Yes   | Retrieve a single page            |
| POST   | /notion/pages                               | Yes   | Create a new page                 |
| PATCH  | /notion/pages/{page_id}                     | Yes   | Update page properties            |

##### Tasks (Task Tracker)
| Method | Path                   | Auth  | Description                              |
|--------|------------------------|-------|------------------------------------------|
| POST   | /notion/tasks/query    | Yes   | Query tasks (auto-pagination)            |
| GET    | /notion/tasks/{id}     | Yes   | Retrieve a task                          |
| POST   | /notion/tasks          | Yes   | Create a task with validated enum fields |
| PATCH  | /notion/tasks/{id}     | Yes   | Update a task                            |

##### Goals (Goals Tracker)
| Method | Path                   | Auth  | Description                              |
|--------|------------------------|-------|------------------------------------------|
| POST   | /notion/goals/query    | Yes   | Query goals (auto-pagination)            |
| GET    | /notion/goals/{id}     | Yes   | Retrieve a goal                          |
| POST   | /notion/goals          | Yes   | Create a goal with validated enum fields |
| PATCH  | /notion/goals/{id}     | Yes   | Update a goal                            |

##### Reading List
| Method | Path                       | Auth  | Description                                   |
|--------|----------------------------|-------|-----------------------------------------------|
| POST   | /notion/reading-list/query | Yes   | Query reading items (auto-pagination)         |
| GET    | /notion/reading-list/{id}  | Yes   | Retrieve a reading item                       |
| POST   | /notion/reading            | Yes   | Create a reading item with validated enums    |
| PATCH  | /notion/reading-list/{id}  | Yes   | Update a reading item                         |

### AI Agent
Standalone AI agent layer that uses AWS Bedrock Converse with tool use to safely execute internal tools. The agent provides structured tool calling via LLMs with validation and safety guardrails.

#### Components
- **ToolRegistry**: Central registry for available tools with JSON schema generation
- **ToolSelector**: AI-first tool selection using Bedrock Converse with fallback to keyword matching
- **BedrockClient**: Typed client for AWS Bedrock Converse API
- **AgentAPIClient**: HTTP client for tools to call internal API endpoints

#### Configuration
- `AWS_REGION`: AWS region for Bedrock (default: eu-west-2)
- `BEDROCK_MODEL_ID`: Model ID for Bedrock Converse (default: Claude Sonnet 4)
- `AGENT_API_BASE_URL`: Base URL for internal API (default: http://localhost:8000)
- `API_AUTH_TOKEN`: Bearer token for API authentication (shared with REST API)

#### Tool Risk Levels
- **Safe**: Read-only or additive operations (e.g., query, get)
- **Sensitive**: Destructive or irreversible operations (e.g., create, update, delete)

#### Available Tools
The agent has 12 built-in tools organised by domain:

| Domain       | Tools                                                    |
|--------------|----------------------------------------------------------|
| Reading List | query_reading_list, get_reading_item, create_reading_item, update_reading_item |
| Goals        | query_goals, get_goal, create_goal, update_goal          |
| Tasks        | query_tasks, get_task, create_task, update_task          |

#### Usage
```python
from src.agent import create_default_registry, ToolSelector, BedrockClient

# Create registry with all tools
registry = create_default_registry()

# Use with ToolSelector for AI-based tool selection
bedrock = BedrockClient()
selector = ToolSelector(registry=registry, client=bedrock)
result = selector.select("Show me my high priority tasks")

# Filter tools by domain
reading_tools = registry.filter_by_tags({"reading"})
goals_tools = registry.filter_by_tags({"goals"})
tasks_tools = registry.filter_by_tags({"tasks"})
```

### Notion Integration
API wrapper for Notion to query and manage tasks, goals, and reading items. The generic endpoints work with any data source, while the typed endpoints use pre-configured data sources with validated field values.

#### Configuration
- `NOTION_INTEGRATION_SECRET`: Notion integration token from https://www.notion.so/my-integrations
- `NOTION_DATABASE_ID`: Database ID for the task tracker (legacy, not used)
- `NOTION_TASK_DATA_SOURCE_ID`: Data source ID for the task tracker
- `NOTION_GOALS_DATA_SOURCE_ID`: Data source ID for the goals tracker
- `NOTION_READING_LIST_DATA_SOURCE_ID`: Data source ID for the reading list

#### Task Fields
Task endpoints validate field values using enums:
- **Status**: Thought, Not started, In progress, Done
- **Priority**: High, Medium, Low
- **Effort level**: Small, Medium, Large
- **Task Group**: Personal, Work, Photography

#### Goal Fields
Goal endpoints validate field values using enums:
- **Status**: Not started, In progress, Done
- **Priority**: High, Medium, Low
- **Progress**: 0-100 (numeric)

#### Reading List Fields
Reading list endpoints validate field values using enums:
- **Status**: To Read, Reading Now, Completed
- **Priority**: High, Medium, Low
- **Category**: Data Analytics, Data Science, Data Engineering, AI

#### Usage
Query tasks:
```bash
curl -X POST http://localhost:8000/notion/tasks/query \
  -H "Authorization: Bearer $API_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filter": {"property": "Status", "status": {"does_not_equal": "Done"}}}'
```

Create a task:
```bash
curl -X POST http://localhost:8000/notion/tasks \
  -H "Authorization: Bearer $API_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_name": "New Task", "status": "Not started", "priority": "High"}'
```

Update a task:
```bash
curl -X PATCH http://localhost:8000/notion/tasks/{task_id} \
  -H "Authorization: Bearer $API_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "Done"}'
```
