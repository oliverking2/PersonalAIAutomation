# PRD24: Update Reminder Functionality

**Status: Up Next**
**Created: 2025-01-11**

## Overview

Extend the existing reminders system (PRD23) to allow updating existing reminders. Users can modify the message, cron schedule, and trigger time through the AI agent.

## Problem Statement

Currently, users can create, query, and cancel reminders, but cannot modify existing ones. If a user sets a recurring reminder for Wednesday but wants it on Tuesday instead, they must:
1. Cancel the existing reminder
2. Create a new one with the correct schedule

This is cumbersome. Users should be able to directly update existing reminders.

## User Stories

1. **As a user**, I want to change when a reminder triggers (e.g., from Wednesday to Tuesday)
2. **As a user**, I want to update the message text of a reminder
3. **As a user**, I want to convert a recurring reminder to one-time (or vice versa)
4. **As a user**, I want to see the full cron schedule when listing reminders so I know what day/time they're set for

## Scope

### In Scope
- Update reminder message
- Update cron schedule (change recurrence pattern)
- Update next trigger time
- Convert recurring to one-time (remove cron)
- Convert one-time to recurring (add cron)
- Enhanced query output to include cron_schedule field

### Out of Scope
- Bulk update operations
- Update reminder chat_id (changing where it's sent)
- Pause/resume functionality (could be future enhancement)

## Technical Design

### Data Model Changes

No database schema changes required. The existing `ReminderSchedule` model already has updateable fields:
- `message` (Text)
- `cron_schedule` (String, nullable)
- `next_trigger_at` (DateTime)

### API Changes

#### New Endpoint: PATCH /reminders/{reminder_id}

```python
class UpdateReminderRequest(BaseModel):
    """Request model for updating a reminder."""

    message: str | None = Field(None, min_length=1, max_length=500, description="New message")
    trigger_at: datetime | None = Field(None, description="New trigger time (ISO format)")
    cron_schedule: str | None = Field(None, description="New cron schedule (empty string to remove)")
```

Response: Returns `ReminderScheduleResponse` with updated values.

**Behaviour:**
- All fields are optional (partial update)
- Only provided fields are updated
- Empty string `""` for `cron_schedule` removes the cron (converts to one-time)
- Returns 404 if reminder not found
- Returns 422 for validation errors

### Database Operation

```python
def update_reminder_schedule(
    session: Session,
    schedule_id: uuid.UUID,
    message: str | None = None,
    cron_schedule: str | None = None,
    next_trigger_at: datetime | None = None,
) -> ReminderSchedule | None:
    """Update a reminder schedule.

    :param session: Database session.
    :param schedule_id: Schedule ID to update.
    :param message: New message (if provided).
    :param cron_schedule: New cron schedule (if provided, empty string clears it).
    :param next_trigger_at: New trigger time (if provided).
    :returns: Updated schedule or None if not found.
    """
```

### Agent Tool

```python
class UpdateReminderArgs(BaseModel):
    """Arguments for updating a reminder."""

    reminder_id: str = Field(..., description="The ID of the reminder to update")
    message: str | None = Field(None, min_length=1, max_length=500, description="New message")
    trigger_at: datetime | None = Field(None, description="New trigger time (ISO 8601)")
    cron_schedule: str | None = Field(None, description="New cron schedule, or empty string to remove")


UPDATE_REMINDER_TOOL = ToolDef(
    name="update_reminder",
    description=(
        "Update an existing reminder's message, schedule, or trigger time. "
        "You can update any combination of fields. To convert a recurring reminder "
        "to one-time, set cron_schedule to empty string. Use query_reminders first "
        "to find the reminder ID if you don't have it."
    ),
    tags=frozenset({"reminders", "update", "edit"}),
    risk_level=RiskLevel.SENSITIVE,
    args_model=UpdateReminderArgs,
    handler=_update_reminder_handler,
)
```

### Enhanced Query Output

The `query_reminders` tool will include `cron_schedule` in its output:

```python
filtered = [
    {
        "id": r.get("id"),
        "message": r.get("message"),
        "next_trigger_at": r.get("next_trigger_at"),
        "cron_schedule": r.get("cron_schedule"),  # NEW
        "is_recurring": r.get("is_recurring"),
        "is_active": r.get("is_active"),
    }
    for r in results
]
```

This allows the agent to display the schedule pattern (e.g., "0 9 * * 3" = Wednesdays at 9am) when listing reminders.

## File Changes

| File | Change |
|------|--------|
| `src/database/reminders/operations.py` | Add `update_reminder_schedule()` |
| `src/database/reminders/__init__.py` | Export new function |
| `src/api/reminders/models.py` | Add `UpdateReminderRequest` |
| `src/api/reminders/endpoints.py` | Add PATCH endpoint |
| `src/agent/tools/reminders.py` | Add update tool, enhance query output |
| `testing/database/reminders/test_operations.py` | Add tests |
| `testing/api/reminders/test_endpoints.py` | Add tests |

## Implementation Phases

### Phase 1: Database Layer
1. Add `update_reminder_schedule()` to operations.py
2. Export from `__init__.py`
3. Unit tests for the operation

### Phase 2: API Layer
4. Add `UpdateReminderRequest` model
5. Add PATCH endpoint
6. API tests

### Phase 3: Agent Layer
7. Add `UpdateReminderArgs` and handler
8. Add `UPDATE_REMINDER_TOOL`
9. Update `get_reminders_tools()` to include new tool
10. Enhance query output with `cron_schedule`

## Testing

### Unit Tests
- Update message only
- Update cron schedule only
- Update trigger time only
- Update multiple fields
- Convert recurring to one-time (empty cron)
- Convert one-time to recurring (add cron)
- Not found returns None/404

### Integration Tests
- End-to-end update via API
- Verify updated values persist

## Success Criteria

1. Users can update reminder message via agent
2. Users can change recurring schedule (e.g., Wednesday to Tuesday)
3. Users can change trigger time for one-time reminders
4. Users can convert between recurring and one-time reminders
5. Query output shows cron schedule for better visibility
6. All changes pass `make check` validation

## Future Enhancements

- Pause/resume reminders without cancelling
- Bulk update operations
- Update timezone per-reminder
- Reminder templates for quick creation
