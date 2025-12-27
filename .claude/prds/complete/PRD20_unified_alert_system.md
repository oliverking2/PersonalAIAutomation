# PRD20: Unified Alert System

**Status: COMPLETED**
**Updated: 2025-12-27**
**Supersedes: PRD04 (Daily Reminders), PRD15 (Newsletter Alert Service)**

## Overview

A unified alert system for sending proactive Telegram notifications. Consolidates newsletter alerts (PRD15) and scheduled reminders (PRD04) into a single, consistent architecture with centralised tracking of all sent alerts.

## Problem Statement

The current and proposed implementations have fragmented approaches:

1. **Newsletter alerts**: Use `alerted_at` on the `Newsletter` model - no centralised tracking
2. **Chat messages**: Use `TelegramMessage` linked to `TelegramSession` - requires conversation context
3. **Reminders (proposed)**: Would need yet another tracking mechanism

This creates:
- Inconsistent tracking patterns across alert types
- No unified view of all outbound notifications
- Duplicated send/track logic in multiple services
- Difficult debugging ("what alerts did we send yesterday?")

## Key Insight

There are two distinct types of outbound Telegram messages:

| Type | Description | Current Tracking |
|------|-------------|-----------------|
| **Conversation messages** | Part of a chat session with the agent | `TelegramMessage` → `TelegramSession` |
| **Standalone alerts** | Proactive notifications, no conversation | Fragmented (`alerted_at`, none) |

This PRD unifies all **standalone alerts** under a single system.

## Alert Types

### 1. Newsletter Alerts
**Trigger**: New newsletter processed (event-driven via Dagster)

Sends formatted newsletter with article links when a new TLDR newsletter is ingested.

### 2. Daily Task Reminder
**Schedule**: Every day at 8:00 AM

Sends a summary of:
- Overdue tasks (past due date, not Done)
- Tasks due today
- High priority tasks due this week

**Example Message**:
```
📋 Daily Task Summary

🔴 OVERDUE (2)
• Review Q4 budget proposal (3 days overdue)
• Reply to Sarah's email (1 day overdue)

📅 DUE TODAY (1)
• Submit expense report

⚡ HIGH PRIORITY THIS WEEK (2)
• Prepare board presentation (Due: Friday)
• Code review for auth refactor (Due: Thursday)
```

### 3. Monthly Goal Review
**Schedule**: 1st of each month at 9:00 AM

Sends a summary of all active goals with progress visualisation.

**Example Message**:
```
🎯 Monthly Goal Review - January 2025

IN PROGRESS (3)
• Learn Spanish basics ━━━━━━━━░░ 75%
  Due: Mar 2025

• Read 24 books this year ━━░░░░░░░░ 17%
  4/24 complete

⚠️ AT RISK (1)
• Complete AWS certification ━━░░░░░░░░ 20%
  Due in 2 weeks, only 20% progress
```

### 4. Weekly Reading List Reminder
**Schedule**: Every Sunday at 6:00 PM

Sends a summary of:
- High priority items marked "To Read"
- Items added more than 30 days ago (getting stale) - based on `last_modified` date

## Architecture

### Database: Unified Alert Tracking

```
src/database/telegram/
├── models.py           # Add SentAlert model
└── operations.py       # Add alert CRUD operations
```

```python
class AlertType(StrEnum):
    """Types of standalone alerts."""

    NEWSLETTER = "newsletter"
    DAILY_TASK = "daily_task"
    MONTHLY_GOAL = "monthly_goal"
    WEEKLY_READING = "weekly_reading"


class SentAlert(Base):
    """Standalone outbound alerts (not part of conversations).

    Tracks all proactive notifications sent via Telegram that are
    not part of an interactive chat session.
    """

    __tablename__ = "sent_alerts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_sent_alerts_type_sent_at", "alert_type", "sent_at"),
        Index("idx_sent_alerts_source_id", "source_id"),
    )
```

**Fields**:
- `alert_type`: Enum identifying the alert category
- `chat_id`: Target Telegram chat
- `content`: Full message content (for audit/debugging)
- `telegram_message_id`: Telegram's message ID (if available from response)
- `source_id`: Optional reference to source record (e.g., newsletter UUID)
- `sent_at`: When the alert was sent

### Domain Module: Unified Alerts

```
src/alerts/
├── __init__.py           # Public exports
├── service.py            # AlertService - orchestrates sending
├── enums.py              # AlertType enum (shared with database)
├── models.py             # Pydantic models for alert data
├── formatters/
│   ├── __init__.py
│   ├── newsletter.py     # format_newsletter_alert()
│   ├── tasks.py          # format_daily_task_alert()
│   ├── goals.py          # format_monthly_goal_alert()
│   └── reading.py        # format_reading_list_alert()
└── providers/
    ├── __init__.py
    ├── newsletter.py     # NewsletterAlertProvider
    ├── tasks.py          # TaskAlertProvider
    ├── goals.py          # GoalAlertProvider
    └── reading.py        # ReadingAlertProvider
```

### Alert Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AlertService                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ send_alerts(alert_type: AlertType) -> SendResult               │ │
│  └────────────────────────────────────────────────────────────────┘ │
│         │                    │                     │                 │
│         ▼                    ▼                     ▼                 │
│   ┌──────────┐        ┌──────────┐          ┌──────────┐            │
│   │ Provider │        │ Formatter│          │ Telegram │            │
│   │ get_data │   →    │ format() │    →     │ send()   │            │
│   └──────────┘        └──────────┘          └──────────┘            │
│                                                   │                  │
│                                                   ▼                  │
│                                            ┌──────────┐             │
│                                            │ Database │             │
│                                            │ track()  │             │
│                                            └──────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### Provider Pattern

Each alert type has a provider that fetches the data needed. Providers inherit from an abstract base class:

```python
from abc import ABC, abstractmethod


class AlertProvider(ABC):
    """Abstract base class for alert data providers."""

    @abstractmethod
    def get_pending_alerts(self) -> list[AlertData]:
        """Fetch data for alerts that should be sent."""
        ...

    @abstractmethod
    def mark_sent(self, source_id: UUID) -> None:
        """Mark the source as alerted (if applicable)."""
        ...


class NewsletterAlertProvider(AlertProvider):
    """Provides newsletter data for alerts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_pending_alerts(self) -> list[NewsletterAlertData]:
        """Get newsletters that haven't been alerted yet."""
        unsent = get_unsent_newsletters(self._session)
        return [NewsletterAlertData.from_orm(n) for n in unsent]

    def mark_sent(self, newsletter_id: UUID) -> None:
        """Mark newsletter as alerted."""
        mark_newsletter_alerted(self._session, newsletter_id)


class TaskAlertProvider(AlertProvider):
    """Provides task data for daily reminders."""

    def __init__(self, api_client: InternalAPIClient) -> None:
        self._api = api_client

    def get_pending_alerts(self) -> list[TaskAlertData]:
        """Get task summary for daily reminder."""
        overdue = self._api.get("/notion/tasks/query", params={"due_before": date.today()})
        due_today = self._api.get("/notion/tasks/query", params={"due_date": date.today()})
        # ... combine into TaskAlertData

    def mark_sent(self, source_id: UUID) -> None:
        """No-op for scheduled reminders (not linked to a source record)."""
        pass
```

### AlertService

```python
class AlertService:
    """Unified service for sending and tracking alerts."""

    def __init__(
        self,
        session: Session,
        telegram_client: TelegramClient,
        api_client: InternalAPIClient | None = None,
    ) -> None:
        self._session = session
        self._telegram = telegram_client
        self._api = api_client
        self._providers = self._init_providers()
        self._formatters = self._init_formatters()

    def send_alerts(self, alert_type: AlertType) -> SendResult:
        """Send all pending alerts of the given type.

        :param alert_type: Type of alerts to send.
        :returns: Result with counts of sent/failed alerts.
        """
        provider = self._providers[alert_type]
        formatter = self._formatters[alert_type]
        result = SendResult()

        pending = provider.get_pending_alerts()
        if not pending:
            logger.info(f"No pending {alert_type.value} alerts")
            return result

        for alert_data in pending:
            try:
                message = formatter(alert_data)
                response = self._telegram.send_message(message)
                self._track_sent_alert(alert_type, message, alert_data.source_id, response)
                provider.mark_sent(alert_data.source_id)
                result.alerts_sent += 1
            except TelegramClientError as e:
                logger.exception(f"Failed to send {alert_type.value} alert: {e}")
                result.errors.append(str(e))

        return result

    def _track_sent_alert(
        self,
        alert_type: AlertType,
        content: str,
        source_id: UUID | None,
        response: TelegramResponse,
    ) -> None:
        """Record the sent alert in the database."""
        create_sent_alert(
            self._session,
            alert_type=alert_type,
            chat_id=self._telegram.chat_id,
            content=content,
            telegram_message_id=response.message_id,
            source_id=source_id,
        )
```

### Dagster Integration

```
src/dagster/alerts/
├── __init__.py
├── definitions.py
├── jobs.py
├── ops.py
└── schedules.py
```

```python
# src/dagster/alerts/ops.py

@op(description="Send alerts of a specific type")
def send_alerts_op(context: OpExecutionContext, alert_type: str) -> None:
    """Generic op for sending any alert type."""
    settings = get_telegram_settings()

    with get_session() as session:
        client = TelegramClient(bot_token=settings.bot_token, chat_id=settings.chat_id)
        api_client = InternalAPIClient() if alert_type != AlertType.NEWSLETTER else None

        service = AlertService(session, client, api_client)
        result = service.send_alerts(AlertType(alert_type))

        context.log.info(f"{alert_type} alerts: sent={result.alerts_sent}, failed={len(result.errors)}")


# Specific ops for each schedule
@op
def send_newsletter_alerts_op(context: OpExecutionContext) -> None:
    send_alerts_op(context, AlertType.NEWSLETTER.value)


@op
def send_daily_task_alerts_op(context: OpExecutionContext) -> None:
    send_alerts_op(context, AlertType.DAILY_TASK.value)
```

```python
# src/dagster/alerts/schedules.py

daily_task_reminder_schedule = ScheduleDefinition(
    job=daily_task_reminder_job,
    cron_schedule="0 8 * * *",
    execution_timezone="Europe/London",
)

monthly_goal_review_schedule = ScheduleDefinition(
    job=monthly_goal_review_job,
    cron_schedule="0 9 1 * *",
    execution_timezone="Europe/London",
)

weekly_reading_reminder_schedule = ScheduleDefinition(
    job=reading_list_reminder_job,
    cron_schedule="0 18 * * 0",
    execution_timezone="Europe/London",
)

# Newsletter alerts triggered by newsletter ingestion job (event-driven)
```

## Migration Path

### Phase 1: API Client & Query Enhancements
1. Move `AgentAPIClient` from `src/agent/api_client.py` to `src/api/client.py` as `InternalAPIClient`
2. Update all agent tool imports to use new location
3. Add `due_before`, `due_after`, `due_date` filters to task query endpoint and tool
4. Add `added_before`, `added_after` filters to reading list query endpoint and tool
5. Write tests for new filters

### Phase 2: Database & Core Infrastructure
6. Create `SentAlert` model in `src/database/telegram/models.py`
7. Add `AlertType` enum to `src/database/telegram/`
8. Create database migration for `sent_alerts` table
9. Add CRUD operations for `SentAlert`

### Phase 3: Alert Module Structure
10. Create `src/alerts/` module structure
11. Implement `AlertService` with provider/formatter pattern
12. Add `NewsletterAlertProvider` and `format_newsletter_alert()`
13. Write unit tests for formatters and service

### Phase 4: Migrate Newsletter Alerts
14. Update Dagster newsletter job to use `AlertService`
15. Backfill `sent_alerts` from existing `alerted_at` data (optional)
16. Remove `TelegramService` from `src/telegram/`
17. Keep `alerted_at` on `Newsletter` for now (remove later)

### Phase 5: Task Reminders
18. Add `TaskAlertProvider` using internal API
19. Implement `format_daily_task_alert()`
20. Create Dagster job and schedule
21. Write integration tests

### Phase 6: Goal & Reading Reminders
22. Add `GoalAlertProvider` and `format_monthly_goal_alert()`
23. Add `ReadingAlertProvider` and `format_reading_list_alert()`
24. Create Dagster jobs and schedules
25. Write integration tests

### Phase 7: Cleanup
26. Remove `alerted_at` from `Newsletter` model (use `sent_alerts` as source of truth)
27. Update documentation

## API & Tool Enhancements

### Task Query Filters

Add date range filters to task querying. These are useful for both alerts and general task management via tools.

**API Endpoint**: `POST /notion/tasks/query`

New query parameters:
- `due_before`: Tasks due before a date (exclusive) - for finding overdue tasks
- `due_after`: Tasks due after a date (exclusive) - for future tasks
- `due_date`: Tasks due on exact date - for "due today" queries

**Agent Tool**: `query_tasks`

Update the tool to expose the same filters:
```python
class QueryTasksArgs(BaseModel):
    """Arguments for querying tasks."""

    status: TaskStatus | None = None
    priority: Priority | None = None
    due_before: date | None = None  # NEW
    due_after: date | None = None   # NEW
    due_date: date | None = None    # NEW
    include_done: bool = False
```

### Reading List Query Filters

Add date filtering for reading list items to find stale items.

**API Endpoint**: `POST /notion/reading-list/query`

New query parameters:
- `added_before`: Items added before a date (based on `last_edited_time`)
- `added_after`: Items added after a date

**Agent Tool**: `query_reading_list`

Update the tool to expose the same filters:
```python
class QueryReadingListArgs(BaseModel):
    """Arguments for querying reading list."""

    status: ReadingStatus | None = None
    item_type: ItemType | None = None
    added_before: date | None = None  # NEW
    added_after: date | None = None   # NEW
```

### Goal Query
Existing `/notion/goals/query` endpoint and `query_goals` tool should already support needed filters (`status`, `include_done`).

### Internal API Client

Move and rename the existing `AgentAPIClient` to be a general-purpose internal API client:

**Current**: `src/agent/api_client.py` → `AgentAPIClient`
**New**: `src/api/client.py` → `InternalAPIClient`

This client is used by:
- Alert providers (for querying tasks/goals/reading list)
- Agent tools (for calling API endpoints)

```python
# src/api/client.py

class InternalAPIClient:
    """HTTP client for calling the internal FastAPI endpoints."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or os.environ.get("API_BASE_URL", "http://localhost:8000")
        # ... existing implementation
```

Agent tools continue to use this client but import from the new location.

## File Changes Summary

| File | Change |
|------|--------|
| `src/database/telegram/models.py` | ADD `SentAlert` model, `AlertType` enum |
| `src/database/telegram/operations.py` | ADD alert CRUD operations |
| `src/alerts/__init__.py` | NEW |
| `src/alerts/service.py` | NEW - `AlertService` |
| `src/alerts/enums.py` | NEW - Re-export `AlertType` |
| `src/alerts/models.py` | NEW - Pydantic models |
| `src/alerts/formatters/*.py` | NEW - Formatter functions |
| `src/alerts/providers/*.py` | NEW - Provider classes |
| `src/dagster/alerts/*.py` | NEW - Jobs, ops, schedules |
| `src/telegram/service.py` | DELETE |
| `src/dagster/newsletters/ops.py` | MODIFY - Use `AlertService` |
| `alembic/versions/xxx_add_sent_alerts.py` | NEW - Migration |
| `src/api/client.py` | NEW - `InternalAPIClient` (moved from agent) |
| `src/agent/api_client.py` | DELETE (moved to `src/api/client.py`) |
| `src/agent/tools/*.py` | MODIFY - Update imports to use `src.api.client` |
| `src/api/notion/tasks/endpoints.py` | MODIFY - Add `due_before`, `due_after`, `due_date` filters |
| `src/api/notion/tasks/models.py` | MODIFY - Add filter fields to query model |
| `src/agent/tools/tasks.py` | MODIFY - Add date filters to `QueryTasksArgs` |
| `src/api/notion/reading_list/endpoints.py` | MODIFY - Add `added_before`, `added_after` filters |
| `src/api/notion/reading_list/models.py` | MODIFY - Add filter fields to query model |
| `src/agent/tools/reading_list.py` | MODIFY - Add date filters to `QueryReadingListArgs` |

## Testing

### Unit Tests
```python
class TestNewsletterFormatter(unittest.TestCase):
    def test_formats_newsletter_with_articles(self): ...
    def test_uses_parsed_url_when_available(self): ...

class TestTaskFormatter(unittest.TestCase):
    def test_formats_overdue_with_days_count(self): ...
    def test_formats_due_today_section(self): ...
    def test_empty_sections_not_shown(self): ...

class TestAlertService(unittest.TestCase):
    def test_sends_and_tracks_alert(self): ...
    def test_handles_send_failure(self): ...
    def test_skips_when_no_pending_alerts(self): ...
```

### Integration Tests
- Test Dagster job execution with mocked providers
- Test alert tracking persists to database
- Test schedule triggers at correct times

## Success Criteria

1. All alert types use unified `AlertService`
2. All sent alerts tracked in `sent_alerts` table
3. Newsletter alerts migrated without behaviour change
4. Daily task reminders sent at 8:00 AM with correct content
5. Monthly goal reviews sent on 1st of month
6. No duplicate alerts sent
7. Empty alerts not sent (no "nothing to report" messages)
8. `TelegramService` removed from codebase

## Future Considerations

- **Quiet hours**: Don't send alerts during specified hours
- **Digest mode**: Combine multiple alert types into single message
- **Retry logic**: Exponential backoff for failed sends
- **Rate limiting**: Respect Telegram rate limits for bulk sends
