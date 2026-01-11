# PRD27: Natural HITL Confirmation Messages

**Status: Complete**
**Created: 2025-01-11**

## Overview

Transform the robotic, computer-generated HITL (Human-in-the-Loop) confirmation messages into natural, conversational prompts that feel more human while still clearly requesting confirmation.

## Problem Statement

Current confirmation messages feel robotic and expose technical implementation details:

```
I need your confirmation to proceed:

update_task: 'Review quarterly report' → due_date='2025-01-01'

Reply 'yes' to confirm or 'no' to cancel.
```

Issues:
1. Technical tool names exposed (`update_task`, `create_reminder`)
2. Arrow notation (`→`) feels like code
3. Formal header ("I need your confirmation to proceed")
4. Explicit instruction on how to respond

## Solution

Transform technical tool calls into human-readable action descriptions using templates.

### Before/After Examples

**Single action:**
```
# Before
I need your confirmation to proceed:

update_task: 'Review quarterly report' → due_date='2025-01-01'

Reply 'yes' to confirm or 'no' to cancel.

# After
I'll update the due date for "Review quarterly report" to 1st Jan 2025 - sound good?
```

**Multiple actions:**
```
# Before
I need your confirmation to proceed with these actions:

1. update_task: 'Review quarterly report' → due_date='2025-01-01'
2. update_goal: 'Learn Spanish' → status='In Progress'

Reply 'yes' to confirm all, 'no' to cancel all,
or specify which to approve (e.g., 'yes to 1 and 2, skip 3').

# After
Just confirming these:

1. Update the due date for "Review quarterly report" to 1st Jan 2025
2. Mark "Learn Spanish" as In Progress
```

**Post-confirmation responses:**
```
# Before (denial)
All actions cancelled.

# After (denial)
No worries, I won't make those changes.

# Before (partial rejection)
All actions were rejected.

# After (partial rejection)
Got it, I'll leave everything as is.
```

## Technical Design

### Sensitive Tools (Require Confirmation)

Based on `RiskLevel.SENSITIVE` in the codebase:

| Tool | Source |
|------|--------|
| `update_task` | factory.py:358 |
| `update_goal` | factory.py:358 |
| `update_reading_item` | factory.py:358 |
| `update_idea` | factory.py:358 |
| `update_reminder` | reminders.py:274 |
| `cancel_reminder` | reminders.py:259 |

Note: All `create_*` tools are `RiskLevel.SAFE` and don't require confirmation.

### Action Templates

**Update operations** - field-specific templates:
| Field | Template |
|-------|----------|
| `due_date` | `update the due date for "{name}" to {date}` |
| `status` | `mark "{name}" as {status}` |
| `priority` | `change the priority of "{name}" to {priority}` |
| Generic | `update "{name}"` + list of changes |

**Cancel operations:**
| Tool | Template |
|------|----------|
| `cancel_reminder` | `cancel the reminder "{message}"` |

**Update reminder:**
| Tool | Template |
|------|----------|
| `update_reminder` | `update the reminder "{message}"` + changes |

Templates are lowercase - the wrapper adds capitalisation as needed.

### Message Format

| Scenario | Format |
|----------|--------|
| Single action | `I'll {action} - sound good?` |
| Multiple actions | `Just confirming these:\n\n1. {Action}\n2. {Action}` |

### Human-Readable Values

Uses `humanize` library for consistent formatting:
- Dates: `2025-01-15` → `15th Jan 2025` (with ordinal suffix)
- Times: `14:30` → `2:30 PM`
- Datetimes: `2025-01-15T14:30:00Z` → `15th Jan 2025 at 2:30 PM`

## File Changes

| File | Change |
|------|--------|
| `src/agent/utils/formatting.py` | **New file** - Action template formatters using `humanize` library |
| `src/agent/runner.py` | Natural post-confirmation responses |
| `src/messaging/telegram/handler.py` | Simplify `_format_confirmation_request()` to use agent formatters |
| `testing/agent/utils/test_formatting.py` | **New file** - Tests for action formatters |
| `testing/messaging/telegram/test_handler.py` | Update tests for new message format |

### Why `src/agent/utils/formatting.py`?

The action formatting logic is about making agent tool actions human-readable - not specific to Telegram:
- Templates are tool-specific ("update the due date for...")
- Could be reused by other messaging providers or API responses
- Follows the existing `src/agent/utils/` pattern for agent utilities

## Implementation

### New Functions in `src/agent/utils/formatting.py`

```python
def format_date_human(iso_date: str) -> str:
    """Convert ISO date to human-readable format."""
    # "2025-01-15" → "15 Jan 2025"

def format_time_human(time_str: str) -> str:
    """Convert 24h time to 12h format."""
    # "14:30" → "2:30 PM"

def format_action(tool_name: str, entity_name: str | None, args: dict) -> str:
    """Format a sensitive tool action as human-readable text (lowercase)."""
    # Returns lowercase action like "update the due date for..."

def format_confirmation_message(actions: list[PendingToolAction]) -> str:
    """Format a confirmation request message."""
    # Returns "Can I {action}?" or "Can I go ahead with these?\n\n1. ..."
```

### Simplified Telegram Handler

```python
from src.agent.utils.formatting import format_confirmation_message

# In _format_confirmation_request():
return format_confirmation_message(pending_actions)
```

## Testing

- Unit tests for each action template
- Unit tests for date/time formatting helpers
- Updated handler tests for new message format

## Success Criteria

- [x] Confirmation messages read naturally ("I'll update the due date... - sound good?")
- [x] No technical tool names exposed to users
- [x] Dates formatted human-readable with ordinals (15th Jan 2025)
- [x] Numbered list preserved for partial approval
- [x] Post-confirmation responses are natural ("No worries, I won't make those changes.")
- [x] All existing handler tests updated and passing
- [x] `make check` passes
