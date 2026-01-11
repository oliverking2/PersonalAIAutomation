# PRD04: Scheduled Task & Goal Reminders

**Status: SUPERSEDED by PRD20**
**Updated: 2024-12-27**

## Overview

Scheduled Telegram notifications to keep track of tasks, goals, and reading list items. Reminders are delivered at configurable times via Dagster scheduled jobs.

## Problem Statement

Without proactive reminders:
1. Overdue tasks go unnoticed until manually checked
2. Goals drift without regular progress review
3. Reading list items accumulate without action
4. No visibility into what needs attention "today"

## Reminder Types

### 1. Daily Task Reminder (Morning)
**Schedule**: Every day at 8:00 AM (configurable)

Sends a summary of:
- Tasks due today
- Overdue tasks (past due date, not Done)
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

### 2. Weekly Task Summary (Optional)
**Schedule**: Every Monday at 9:00 AM

Sends a summary of:
- Tasks planned for this week
- Overdue task count

### 3. Monthly Goal Review
**Schedule**: 1st of each month at 9:00 AM

Sends a summary of all active goals with:
- Goal name and progress percentage
- Status (Not Started, In Progress, etc.)
- Due date if set
- Goals at risk (low progress, approaching deadline)

**Example Message**:
```
🎯 Monthly Goal Review - January 2025

IN PROGRESS (3)
• Learn Spanish basics ━━━━━━━━░░ 75%
  Status: In Progress | Due: Mar 2025

• Improve fitness ━━━━━░░░░░ 45%
  Status: In Progress | Due: Jun 2025

• Read 24 books this year ━━░░░░░░░░ 17%
  Status: In Progress | 4/24 complete

⚠️ AT RISK (1)
• Complete AWS certification ━━░░░░░░░░ 20%
  Due in 2 weeks, only 20% progress

NOT STARTED (1)
• Build personal website
  No due date set
```

### 4. Reading List Reminder (Weekly)
**Schedule**: Every Sunday at 6:00 PM

Sends a summary of:
- Items marked "To Read" with high priority
- Items added more than 30 days ago (getting stale)
- Reading streak/progress if applicable

## Architecture

### Integration with Existing Systems

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Dagster Job    │────▶│  Notion API     │────▶│  NotionClient   │
│  (Scheduled)    │     │  (Query Tasks/  │     │  (Existing)     │
└────────┬────────┘     │   Goals)        │     └─────────────────┘
         │              └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Reminder       │────▶│  TelegramService│
│  Service        │     │  (via PRD15)    │
└─────────────────┘     └─────────────────┘
```

### Key Design Decisions

1. **Use Internal API**: Query tasks/goals via the FastAPI endpoints (not direct Notion calls)
   - Benefit: Reuses existing query logic, filters, and validation
   - Benefit: Consistent with agent tool architecture

2. **Service Layer**: New `ReminderService` handles formatting and orchestration
   - Follows same pattern as `NewsletterAlertService` (PRD15)
   - Uses `TelegramService` for message delivery (not `TelegramClient` directly)

3. **Dependency**: Implement PRD15 first to establish the simplified `TelegramService` pattern

4. **Dagster Orchestration**: Schedules and jobs in `src/dagster/reminders/`
   - Follows existing newsletter pattern

## Implementation

### New Files

```
src/reminders/
├── __init__.py
├── service.py          # ReminderService class
├── formatters.py       # Message formatting functions
└── models.py           # Pydantic models for reminder data

src/dagster/reminders/
├── __init__.py
├── definitions.py      # Dagster definitions
├── jobs.py             # Job definitions
├── ops.py              # Dagster ops
└── schedules.py        # Cron schedules
```

### ReminderService

```python
class ReminderService:
    """Service for generating and sending reminder notifications."""

    def __init__(
        self,
        api_client: AgentAPIClient,
        telegram_client: TelegramClient,
    ) -> None:
        self._api = api_client
        self._telegram = telegram_client

    def send_daily_task_reminder(self) -> SendResult:
        """Send daily task reminder with overdue and due-today tasks."""
        # Query overdue tasks
        overdue = self._query_tasks(due_before=date.today(), include_done=False)

        # Query due today
        due_today = self._query_tasks(due_date=date.today(), include_done=False)

        # Query high priority this week
        high_priority = self._query_tasks(
            priority="High",
            due_before=date.today() + timedelta(days=7),
            include_done=False,
        )

        if not overdue and not due_today and not high_priority:
            return SendResult()  # Nothing to send

        message = format_daily_task_message(overdue, due_today, high_priority)
        self._telegram.send_message(message)

        return SendResult(reminders_sent=1)

    def send_monthly_goal_review(self) -> SendResult:
        """Send monthly goal progress review."""
        goals = self._query_goals(include_done=False)

        if not goals:
            return SendResult()

        message = format_monthly_goal_message(goals)
        self._telegram.send_message(message)

        return SendResult(reminders_sent=1)
```

### Message Formatters

```python
def format_daily_task_message(
    overdue: list[TaskResponse],
    due_today: list[TaskResponse],
    high_priority: list[TaskResponse],
) -> str:
    """Format daily task reminder message."""
    lines = ["📋 <b>Daily Task Summary</b>", ""]

    if overdue:
        lines.append(f"🔴 <b>OVERDUE ({len(overdue)})</b>")
        for task in overdue:
            days = (date.today() - task.due_date).days
            lines.append(f"• {task.task_name} ({days} days overdue)")
        lines.append("")

    if due_today:
        lines.append(f"📅 <b>DUE TODAY ({len(due_today)})</b>")
        for task in due_today:
            lines.append(f"• {task.task_name}")
        lines.append("")

    if high_priority:
        lines.append(f"⚡ <b>HIGH PRIORITY THIS WEEK ({len(high_priority)})</b>")
        for task in high_priority:
            due_str = task.due_date.strftime("%A") if task.due_date else "No date"
            lines.append(f"• {task.task_name} (Due: {due_str})")

    return "\n".join(lines).strip()


def format_monthly_goal_message(goals: list[GoalResponse]) -> str:
    """Format monthly goal review message."""
    today = date.today()
    lines = [f"🎯 <b>Monthly Goal Review - {today.strftime('%B %Y')}</b>", ""]

    # Group by status
    in_progress = [g for g in goals if g.status == "In Progress"]
    not_started = [g for g in goals if g.status == "Not Started"]
    at_risk = _identify_at_risk_goals(goals)

    if in_progress:
        lines.append(f"<b>IN PROGRESS ({len(in_progress)})</b>")
        for goal in in_progress:
            lines.append(_format_goal_line(goal))
        lines.append("")

    if at_risk:
        lines.append(f"⚠️ <b>AT RISK ({len(at_risk)})</b>")
        for goal in at_risk:
            lines.append(_format_goal_line(goal, show_risk=True))
        lines.append("")

    if not_started:
        lines.append(f"<b>NOT STARTED ({len(not_started)})</b>")
        for goal in not_started:
            lines.append(f"• {goal.goal_name}")

    return "\n".join(lines).strip()


def _format_goal_line(goal: GoalResponse, show_risk: bool = False) -> str:
    """Format a single goal with progress bar."""
    progress = goal.progress or 0
    filled = int(progress / 10)
    empty = 10 - filled
    bar = "━" * filled + "░" * empty

    line = f"• {goal.goal_name} {bar} {progress:.0f}%"

    if goal.due_date:
        line += f"\n  Due: {goal.due_date.strftime('%b %Y')}"

    return line


def _identify_at_risk_goals(goals: list[GoalResponse]) -> list[GoalResponse]:
    """Identify goals that are at risk of not being completed."""
    at_risk = []
    today = date.today()

    for goal in goals:
        if goal.status != "In Progress":
            continue

        if goal.due_date and goal.progress:
            days_remaining = (goal.due_date - today).days
            # At risk if < 30 days remaining and < 50% progress
            if days_remaining < 30 and goal.progress < 50:
                at_risk.append(goal)

    return at_risk
```

### Dagster Jobs

```python
# src/dagster/reminders/jobs.py

from dagster import job

from src.dagster.reminders.ops import (
    send_daily_task_reminder_op,
    send_monthly_goal_review_op,
    send_reading_list_reminder_op,
)


@job(description="Send daily task reminder via Telegram")
def daily_task_reminder_job():
    send_daily_task_reminder_op()


@job(description="Send monthly goal review via Telegram")
def monthly_goal_review_job():
    send_monthly_goal_review_op()


@job(description="Send weekly reading list reminder via Telegram")
def reading_list_reminder_job():
    send_reading_list_reminder_op()
```

### Dagster Schedules

```python
# src/dagster/reminders/schedules.py

from dagster import ScheduleDefinition

from src.dagster.reminders.jobs import (
    daily_task_reminder_job,
    monthly_goal_review_job,
    reading_list_reminder_job,
)

# Daily at 8:00 AM UK time
daily_task_reminder_schedule = ScheduleDefinition(
    job=daily_task_reminder_job,
    cron_schedule="0 8 * * *",
    execution_timezone="Europe/London",
)

# 1st of each month at 9:00 AM UK time
monthly_goal_review_schedule = ScheduleDefinition(
    job=monthly_goal_review_job,
    cron_schedule="0 9 1 * *",
    execution_timezone="Europe/London",
)

# Every Sunday at 6:00 PM UK time
reading_list_reminder_schedule = ScheduleDefinition(
    job=reading_list_reminder_job,
    cron_schedule="0 18 * * 0",
    execution_timezone="Europe/London",
)
```

## Configuration

### Environment Variables

```bash
# Reminder schedules (override defaults)
DAILY_REMINDER_HOUR=8          # Hour for daily reminders (0-23)
MONTHLY_REMINDER_DAY=1         # Day of month for goal review (1-28)
REMINDER_TIMEZONE=Europe/London

# Feature flags
ENABLE_DAILY_REMINDERS=true
ENABLE_MONTHLY_GOAL_REVIEW=true
ENABLE_READING_REMINDERS=true
```

## API Enhancements Needed

### Task Query Enhancements
The existing `/notion/tasks/query` endpoint may need:
- `due_before` filter (tasks due before a date)
- `due_after` filter (tasks due after a date)
- `due_date` exact match filter

### Goal Query Enhancements
The existing `/notion/goals/query` endpoint should already support:
- `include_done` filter ✓
- `status` filter ✓

## Testing

### Unit Tests

```python
class TestReminderFormatters(unittest.TestCase):
    def test_format_daily_task_message_with_overdue(self):
        """Test daily message includes overdue tasks."""
        overdue = [TaskResponse(task_name="Test task", due_date=date.today() - timedelta(days=2))]
        message = format_daily_task_message(overdue, [], [])
        self.assertIn("OVERDUE", message)
        self.assertIn("2 days overdue", message)

    def test_format_monthly_goal_message_with_progress(self):
        """Test monthly message shows progress bars."""
        goals = [GoalResponse(goal_name="Test goal", progress=75, status="In Progress")]
        message = format_monthly_goal_message(goals)
        self.assertIn("━━━━━━━", message)
        self.assertIn("75%", message)

    def test_identify_at_risk_goals(self):
        """Test at-risk detection for low progress near deadline."""
        goals = [
            GoalResponse(
                goal_name="At risk goal",
                progress=20,
                status="In Progress",
                due_date=date.today() + timedelta(days=14),
            )
        ]
        at_risk = _identify_at_risk_goals(goals)
        self.assertEqual(len(at_risk), 1)
```

### Integration Tests

- Test Dagster job execution with mocked API
- Test schedule triggers at correct times
- Test Telegram message delivery

## Implementation Phases

### Phase 1: Core Infrastructure
1. Create `src/reminders/` module structure
2. Implement `ReminderService` class
3. Add message formatters for tasks and goals
4. Write unit tests for formatters

### Phase 2: Daily Task Reminders
5. Implement `send_daily_task_reminder` method
6. Add `due_before`/`due_after` filters to task query endpoint
7. Create Dagster job and schedule
8. Test end-to-end flow

### Phase 3: Monthly Goal Review
9. Implement `send_monthly_goal_review` method
10. Add at-risk goal detection logic
11. Create Dagster job and schedule
12. Test end-to-end flow

### Phase 4: Reading List & Polish
13. Implement reading list reminder (optional)
14. Add configuration options
15. Add feature flags for enabling/disabling reminders
16. Documentation and monitoring

## Success Criteria

1. Daily task reminders sent at configured time with overdue and due-today tasks
2. Monthly goal reviews sent on 1st of month with progress visualisation
3. At-risk goals flagged when approaching deadline with low progress
4. No duplicate reminders sent
5. Graceful handling when no items to remind about (no empty messages)
6. Configurable schedules via environment variables

## Future Considerations

- **Smart Reminders**: Use AI to prioritise which tasks/goals to highlight
- **Snooze**: Allow user to snooze reminders via Telegram reply
- **Custom Schedules**: Per-task or per-goal reminder schedules
- **Digest Mode**: Combine all reminders into a single daily digest
- **Progress Trends**: Show goal progress trends over time (improving/declining)
