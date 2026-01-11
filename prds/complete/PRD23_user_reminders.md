# PRD23: User-Configurable Reminders

**Status: Complete (Phases 1-4)**
**Created: 2025-01-06**
**Completed: 2025-01-06**

## Overview

A reminder system allowing users to set one-time and recurring reminders via the AI agent. Reminders are delivered via Telegram, repeating every 30 minutes until acknowledged (max 3 attempts total).

## Problem Statement

Currently, the system supports scheduled task/goal alerts (PRD20), but these are system-driven based on due dates. Users cannot:
1. Set ad-hoc reminders for arbitrary things ("remind me to call Mum at 7pm")
2. Create recurring reminders not tied to Notion tasks ("remind me to take vitamins every morning")
3. Receive persistent nudges until they acknowledge completion

## User Stories

1. **As a user**, I want to say "remind me to <do something> at 7am tomorrow" and receive a Telegram message at that time.
2. **As a user**, I want to set recurring reminders like "remind me every weekday at 9am to check emails".
3. **As a user**, I want all reminders to keep nudging me every 30 minutes until I acknowledge them (max 3 times).
4. **As a user**, I want to snooze a reminder when I'm busy.
5. **As a user**, I want to list, edit, and cancel my pending reminders.

## Reminder Types

### 1. One-Time Reminders
- Triggers at a specific date/time
- Re-sends every 30 minutes if not acknowledged
- Maximum 3 attempts total (1.5 hours of nudging)
- Expires after max attempts (kept in database for history)

### 2. Recurring Reminders
- Triggers on a cron schedule (stored in database)
- Also requires acknowledgement (re-sends until acknowledged or expired)
- After acknowledgement/expiry, schedules next occurrence
- Can be paused/resumed
- Common patterns the agent can build:
  - Daily at specific time (`0 9 * * *`)
  - Weekdays only (`0 9 * * 1-5`)
  - Weekends only (`0 9 * * 0,6`)
  - Weekly on specific day(s) (`0 9 * * 1` = Monday 9am)
  - Monthly on specific day (`0 9 15 * *` = 15th at 9am)

## Data Model

### Tables

Two tables: `reminder_schedules` for the schedule definitions, and `reminder_instances` for each triggered instance that needs acknowledgement.

```python
class ReminderStatus(StrEnum):
    PENDING = "pending"         # Waiting to trigger
    ACTIVE = "active"           # Has triggered, awaiting acknowledgement
    SNOOZED = "snoozed"         # Temporarily delayed
    ACKNOWLEDGED = "acknowledged"  # User confirmed
    EXPIRED = "expired"         # Max attempts reached without acknowledgement


class ReminderSchedule(Base):
    """Defines when reminders should trigger (one-time or recurring)."""
    __tablename__ = "reminder_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Core fields
    message: Mapped[str] = mapped_column(Text, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Scheduling - cron for recurring, specific datetime for one-time
    cron_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Examples: "0 9 * * *" (daily 9am), "0 9 * * 1-5" (weekdays 9am), NULL for one-time
    next_trigger_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Timezone hardcoded to Europe/London for cron evaluation

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # False = paused (for recurring) or completed/cancelled (for one-time)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    instances: Mapped[list["ReminderInstance"]] = relationship(back_populates="schedule")

    __table_args__ = (
        Index("idx_reminder_schedules_next_trigger", "next_trigger_at", "is_active"),
        Index("idx_reminder_schedules_chat_id", "chat_id"),
    )


class ReminderInstance(Base):
    """A triggered reminder instance awaiting acknowledgement."""
    __tablename__ = "reminder_instances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Link to schedule
    schedule_id: Mapped[UUID] = mapped_column(ForeignKey("reminder_schedules.id"), nullable=False)
    schedule: Mapped["ReminderSchedule"] = relationship(back_populates="instances")

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_sends: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 3 attempts total
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Completion tracking
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_reminder_instances_status_next_send", "status", "next_send_at"),
        Index("idx_reminder_instances_schedule_id", "schedule_id"),
    )
```

### How It Works

1. **One-time reminder**: `ReminderSchedule` with `cron_schedule=NULL`, creates one `ReminderInstance`
2. **Recurring reminder**: `ReminderSchedule` with `cron_schedule` set, creates new `ReminderInstance` each trigger
3. **Acknowledgement**: Marks instance as acknowledged, for recurring schedules calculates next trigger
4. **Expiry**: After 3 sends without acknowledgement, instance marked expired (kept for history)

## Architecture

### Component Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Agent Tools    │────▶│  API Endpoints  │────▶│  Database       │
│  (CRUD)         │     │  /reminders/*   │     │  (PostgreSQL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Dagster Job    │────▶│  Reminder       │────▶│  Telegram       │
│  (every 5 min)  │     │  Service        │     │  Service        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │  Acknowledgement│
                        │  Handler        │
                        └─────────────────┘
```

### Data Flow

1. **Creation**: User → Agent → API → Database
2. **Delivery**: Dagster (5min) → Service → Check pending → Send via Telegram → Update status
3. **Acknowledgement**: Telegram callback → API → Update status
4. **Recurring Reset**: After each send, calculate next trigger time

### Key Design Decisions

1. **Dagster polling (5 min)**: Simple, reliable, no need for real-time precision
   - Trade-off: Reminders may be up to 5 minutes late
   - Alternative considered: APScheduler or Celery beat (more complex)

2. **Telegram inline buttons for acknowledgement**: User taps button to acknowledge
   - Callback goes directly to dedicated handler, NOT through agent conversation
   - This avoids triggering agent responses when acknowledging/snoozing
   - Alternatives: Reply with specific text, separate command

3. **30-minute re-send interval**: Persistent but not overwhelming
   - Configurable per-reminder if needed

4. **Timezone handling**: Store timestamps in UTC, evaluate cron schedules in Europe/London
   - Hardcoded to Europe/London (not configurable)

## API Endpoints

### POST /reminders
Create a new reminder.

```python
class CreateReminderRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    trigger_at: datetime  # ISO format with timezone, for first trigger
    cron_schedule: str | None = None  # NULL for one-time, cron expression for recurring

class ReminderResponse(BaseModel):
    id: UUID
    message: str
    next_trigger_at: datetime
    cron_schedule: str | None
    is_recurring: bool
    is_active: bool
    created_at: datetime
```

### GET /reminders
List reminder schedules with optional filters.

```python
class QueryRemindersRequest(BaseModel):
    include_inactive: bool = False  # Include completed/cancelled
    limit: int = Field(default=20, le=100)
```

### GET /reminders/{reminder_id}
Get a specific reminder.

### PATCH /reminders/{reminder_id}
Update a reminder (message, trigger_at, recurrence).

### DELETE /reminders/{reminder_id}
Cancel/delete a reminder.

### POST /reminders/{reminder_id}/acknowledge
Acknowledge a reminder (stops re-sending).

### POST /reminders/{reminder_id}/snooze
Snooze a reminder.

```python
class SnoozeRequest(BaseModel):
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    # Or use predefined options:
    snooze_option: Literal["15min", "1hour", "3hours", "tomorrow_morning"] | None = None
```

## Agent Tools

Following the CRUD factory pattern:

### Tool: `create_reminder`
```
Create a reminder to be sent at a specific time.

Arguments:
- message (required): What to remind about
- trigger_at (required): When to send (ISO datetime or natural language)
- recurrence: "none", "daily", "weekdays", "weekends", "weekly", "monthly"
- recurrence_days: Days for weekly (0-6, Mon=0) or monthly (1-31)

Examples:
- "remind me to call Mum" at "2025-01-07T19:00:00"
- "take vitamins" daily at 08:00
- "team standup" weekdays at 09:30
```

### Tool: `query_reminders`
```
List pending and active reminders.

Arguments:
- status: Filter by status (pending, active, snoozed)
- include_completed: Include acknowledged/expired reminders
```

### Tool: `cancel_reminder`
```
Cancel a pending or active reminder.

Arguments:
- reminder_id: ID of the reminder to cancel
```

### Tool: `snooze_reminder`
```
Snooze an active reminder.

Arguments:
- reminder_id: ID of the reminder to snooze
- duration: "15min", "1hour", "3hours", "tomorrow_morning", or minutes
```

## Reminder Service

```python
class ReminderService:
    """Service for processing and sending reminders."""

    def __init__(
        self,
        session: Session,
        telegram_service: TelegramService,
    ) -> None:
        self._session = session
        self._telegram = telegram_service

    def process_due_reminders(self) -> ProcessResult:
        """Process all reminders due for sending.

        Returns:
            ProcessResult with counts of sent, skipped, expired.
        """
        now = datetime.now(UTC)

        # Get reminders where:
        # 1. status is 'pending' and trigger_at <= now
        # 2. status is 'active' and last_sent_at + 30min <= now and send_count < max_sends
        # 3. status is 'snoozed' and snoozed_until <= now

        due_reminders = self._get_due_reminders(now)

        sent = 0
        expired = 0

        for reminder in due_reminders:
            if reminder.send_count >= reminder.max_sends:
                self._expire_reminder(reminder)
                expired += 1
                continue

            self._send_reminder(reminder)
            sent += 1

        return ProcessResult(sent=sent, expired=expired)

    def _send_reminder(self, reminder: Reminder) -> None:
        """Send a reminder via Telegram with acknowledge button."""
        message = self._format_message(reminder)
        keyboard = self._build_keyboard(reminder)

        self._telegram.send_message(
            chat_id=reminder.chat_id,
            text=message,
            reply_markup=keyboard,
        )

        reminder.status = ReminderStatus.ACTIVE
        reminder.send_count += 1
        reminder.last_sent_at = datetime.now(UTC)

        if reminder.recurrence_type != RecurrenceType.NONE:
            # For recurring, reset and schedule next
            self._schedule_next_occurrence(reminder)

    def _format_message(self, reminder: Reminder) -> str:
        """Format reminder message with metadata."""
        lines = [
            f"<b>Reminder</b>",
            f"",
            f"{reminder.message}",
        ]

        if reminder.send_count > 0:
            lines.append(f"")
            lines.append(f"<i>(Reminder #{reminder.send_count + 1})</i>")

        return "\n".join(lines)

    def _build_keyboard(self, reminder: Reminder) -> InlineKeyboardMarkup:
        """Build inline keyboard with acknowledge and snooze buttons."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Done",
                    callback_data=f"remind:ack:{reminder.id}",
                ),
                InlineKeyboardButton(
                    text="Snooze 1h",
                    callback_data=f"remind:snooze:{reminder.id}:60",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Snooze 3h",
                    callback_data=f"remind:snooze:{reminder.id}:180",
                ),
                InlineKeyboardButton(
                    text="Tomorrow",
                    callback_data=f"remind:snooze:{reminder.id}:tomorrow",
                ),
            ],
        ])
```

## Dagster Job

```python
# src/dagster/reminders/jobs.py

@job(
    name="process_reminders_job",
    description="Process and send due reminders (runs every 5 minutes).",
)
def process_reminders_job() -> None:
    process_reminders_op()


# src/dagster/reminders/schedules.py

process_reminders_schedule = ScheduleDefinition(
    job=process_reminders_job,
    cron_schedule="*/5 * * * *",  # Every 5 minutes
    execution_timezone="UTC",     # Use UTC for consistency
)
```

## Telegram Callback Handler

Handle inline button callbacks for acknowledgement and snoozing:

```python
async def handle_reminder_callback(
    callback_query: CallbackQuery,
    session: Session,
) -> None:
    """Handle reminder callback buttons."""
    data = callback_query.data
    # Format: remind:action:reminder_id[:param]

    parts = data.split(":")
    action = parts[1]
    reminder_id = UUID(parts[2])

    reminder = get_reminder_by_id(session, reminder_id)
    if not reminder:
        await callback_query.answer("Reminder not found")
        return

    if action == "ack":
        acknowledge_reminder(session, reminder_id)
        await callback_query.answer("Reminder acknowledged!")
        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n<i>Acknowledged</i>",
            parse_mode="HTML",
        )

    elif action == "snooze":
        duration = parts[3]
        if duration == "tomorrow":
            # Calculate tomorrow 8am
            snooze_until = _get_tomorrow_morning()
        else:
            snooze_until = datetime.now(UTC) + timedelta(minutes=int(duration))

        snooze_reminder(session, reminder_id, snooze_until)
        await callback_query.answer(f"Snoozed until {snooze_until.strftime('%H:%M')}")
```

## Additional Features

### 1. Natural Language Date Parsing
Parse common patterns in agent tool:

```python
def parse_reminder_time(text: str, reference: datetime) -> datetime:
    """Parse natural language time expressions.

    Examples:
    - "7am tomorrow" -> tomorrow at 07:00
    - "in 2 hours" -> now + 2 hours
    - "next Monday at 9am" -> following Monday at 09:00
    - "every morning" -> recurring daily at 08:00
    """
    # Use dateparser or custom logic
```

### 2. Reminder Summary (Future)
Daily summary of upcoming reminders:

```
Your reminders for today:
- 09:00: Team standup
- 14:00: Call dentist
- 18:00: Pick up dry cleaning

Recurring reminders:
- Daily 08:00: Take vitamins
- Weekdays 09:30: Check emails
```

### 3. Quick Actions
The agent should understand shorthand patterns:

```
"remind me in 1 hour to check the oven"
"remind me tomorrow morning to reply to Sarah"
"remind me every day at 8am to take vitamins"
```

### 4. Reminder Categories (Future)
Group reminders by category for organisation:

```python
class ReminderCategory(StrEnum):
    GENERAL = "general"
    HEALTH = "health"
    WORK = "work"
    PERSONAL = "personal"
```

## File Structure

```
src/reminders/
├── __init__.py
├── service.py          # ReminderService class
├── models.py           # Pydantic models
└── enums.py            # RecurrenceType, ReminderStatus

src/database/reminders/
├── __init__.py
├── models.py           # SQLAlchemy Reminder model
└── operations.py       # CRUD operations

src/api/reminders/
├── __init__.py
├── router.py           # FastAPI router
├── endpoints.py        # Route handlers
└── models.py           # Request/response models

src/agent/tools/
└── reminders.py        # Agent tool definitions

src/dagster/reminders/
├── __init__.py
├── definitions.py      # Dagster definitions
├── jobs.py             # Job definitions
├── ops.py              # Dagster ops
└── schedules.py        # 5-minute schedule

src/telegram/
└── callbacks.py        # Add reminder callback handling
```

## Configuration

```bash
# Reminder settings
REMINDER_CHECK_INTERVAL_MINUTES=5
REMINDER_RESEND_INTERVAL_MINUTES=30
REMINDER_MAX_SENDS_DEFAULT=3
```

Note: Timezone is hardcoded to `Europe/London` (not configurable).

## Implementation Phases

### Phase 1: Core Infrastructure
1. Database model and migrations
2. CRUD operations
3. API endpoints (create, list, get, delete)
4. Basic unit tests

### Phase 2: Agent Integration
5. Agent tools (create_reminder, query_reminders, cancel_reminder)
6. Date/time parsing helpers
7. Integration with existing tool factory

### Phase 3: Delivery System
8. ReminderService with send logic
9. Dagster job and schedule
10. Telegram message formatting

### Phase 4: Acknowledgement & Snooze
11. Inline keyboard buttons
12. Callback handler for ack/snooze
13. Snooze logic and re-scheduling

### Phase 5: Recurring Reminders
14. Recurrence type handling
15. Next occurrence calculation
16. DST-aware time handling

### Phase 6: Polish
17. Natural language parsing improvements
18. Documentation and monitoring

## Testing

### Unit Tests
- Reminder CRUD operations
- Next occurrence calculation (cron parsing)
- Message formatting
- Snooze and acknowledgement logic

### Integration Tests
- End-to-end reminder creation via agent
- Dagster job execution
- Telegram callback handling

## Success Criteria

1. Users can create one-time reminders via agent with specific date/time
2. Users can create recurring reminders (daily, weekdays, weekly) using cron schedules
3. All reminders re-send every 30 minutes until acknowledged (max 3 times)
4. Users can snooze reminders via Telegram inline buttons
5. Users can list and cancel pending reminders via agent
6. Reminders are processed within 5 minutes of their trigger time
7. Expired reminders are kept in database for history (not deleted)

## Future Enhancements

- **Location-based reminders**: "Remind me when I get home" (requires location tracking)
- **Linked to tasks**: "Remind me about task X tomorrow" (links reminder to Notion task)
- **Smart timing**: AI suggests optimal reminder times based on patterns
- **Voice reminders**: Telegram voice message reminders
- **Escalation**: If reminder not acknowledged, escalate (call? email?)
- **Shared reminders**: Remind multiple people (would need multi-user support)
