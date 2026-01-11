"""Human-readable formatting for agent tool actions.

Provides templates for formatting sensitive tool actions into natural language
for HITL (Human-in-the-Loop) confirmation messages.
"""

from datetime import datetime
from typing import Any

import humanize

from src.agent.models import PendingToolAction

# Length to truncate reminder IDs to when displaying fallback
SHORT_ID_LENGTH = 8

# Maximum length for content before truncation in HITL messages
CONTENT_TRUNCATION_LENGTH = 50

# Maximum length for content in diff display before truncation
DIFF_CONTENT_TRUNCATION_LENGTH = 200


def format_date_human(iso_date: str) -> str:
    """Convert ISO date to human-readable format with ordinal day.

    :param iso_date: Date string in ISO format (YYYY-MM-DD or full datetime).
    :returns: Human-readable date like "15th Jan 2025".
    """
    try:
        # Handle both date-only and datetime strings
        if "T" in iso_date:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_date)
        return f"{humanize.ordinal(dt.day)} {dt.strftime('%b %Y')}"
    except (ValueError, AttributeError):
        # Return as-is if parsing fails
        return iso_date


def format_time_human(time_str: str | datetime) -> str:
    """Convert time to human-readable 12-hour format.

    :param time_str: Time string or datetime object.
    :returns: Human-readable time like "2:30 PM".
    """
    try:
        if isinstance(time_str, datetime):
            dt = time_str
        elif "T" in str(time_str):
            dt = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
        else:
            # Assume time-only string like "14:30"
            dt = datetime.strptime(str(time_str), "%H:%M")
        return dt.strftime("%-I:%M %p")
    except (ValueError, AttributeError):
        return str(time_str)


def format_datetime_human(dt_str: str | datetime) -> str:
    """Convert datetime to human-readable format with ordinal day.

    :param dt_str: Datetime string or datetime object.
    :returns: Human-readable datetime like "15th Jan 2025 at 2:30 PM".
    """
    try:
        if isinstance(dt_str, datetime):
            dt = dt_str
        else:
            dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        return f"{humanize.ordinal(dt.day)} {dt.strftime('%b %Y')} at {dt.strftime('%-I:%M %p')}"
    except (ValueError, AttributeError):
        return str(dt_str)


def _format_value(key: str, value: Any) -> str:
    """Format a single argument value for display.

    :param key: The argument key name.
    :param value: The argument value.
    :returns: Human-readable formatted value.
    """
    # Format dates
    if key in ("due_date", "date") and isinstance(value, str):
        return format_date_human(value)

    # Format datetimes
    if key in ("trigger_at", "next_trigger_at") and value:
        return format_datetime_human(value)

    # Truncate long content fields
    if key == "content" and isinstance(value, str) and len(value) > CONTENT_TRUNCATION_LENGTH:
        return f"{value[:CONTENT_TRUNCATION_LENGTH].strip()}..."

    # Return as-is for other types
    return str(value)


def _format_single_field_update(
    entity_name: str | None,
    field: str,
    formatted_value: str,
) -> str:
    """Format a single-field update into natural language.

    :param entity_name: The name of the entity being updated.
    :param field: The field being updated.
    :param formatted_value: The formatted new value.
    :returns: Lowercase action description.
    """
    if not entity_name:
        return f"update {field} to {formatted_value}"

    # Field-specific templates for named entities
    field_templates = {
        "due_date": f'update the due date for "{entity_name}" to {formatted_value}',
        "status": f'mark "{entity_name}" as {formatted_value}',
        "priority": f'change the priority of "{entity_name}" to {formatted_value}',
        "content": f'update the description for "{entity_name}"',
    }

    return field_templates.get(field, f'update "{entity_name}" ({field}: {formatted_value})')


def _format_update_action(entity_name: str | None, args: dict[str, Any]) -> str:
    """Format an update action into natural language.

    :param entity_name: The name of the entity being updated (e.g., task name).
    :param args: The update arguments (excluding the entity ID).
    :returns: Lowercase action description.
    """
    # Remove ID fields from args for display
    display_args = {k: v for k, v in args.items() if not k.endswith("_id")}

    # No actual changes specified
    if not display_args:
        return f'update "{entity_name}"' if entity_name else "update item"

    # Single field updates get specific templates
    if len(display_args) == 1:
        field, value = next(iter(display_args.items()))
        return _format_single_field_update(entity_name, field, _format_value(field, value))

    # Multiple fields - list them
    changes = [f"{k}: {_format_value(k, v)}" for k, v in display_args.items()]
    changes_str = ", ".join(changes)

    return (
        f'update "{entity_name}" ({changes_str})' if entity_name else f"update item ({changes_str})"
    )


def _format_cancel_action(entity_name: str | None, args: dict[str, Any]) -> str:
    """Format a cancel action into natural language.

    :param entity_name: The name of the entity being cancelled.
    :param args: The cancel arguments.
    :returns: Lowercase action description.
    """
    if entity_name:
        return f'cancel the reminder "{entity_name}"'

    # Fall back to showing the ID if we don't have the name
    reminder_id = args.get("reminder_id", "")
    if reminder_id:
        short_id = (
            reminder_id[:SHORT_ID_LENGTH] if len(reminder_id) > SHORT_ID_LENGTH else reminder_id
        )
        return f"cancel reminder {short_id}..."
    return "cancel reminder"


def format_action(
    tool_name: str,
    entity_name: str | None,
    args: dict[str, Any],
) -> str:
    """Format a tool action as human-readable text (lowercase).

    :param tool_name: The name of the tool (e.g., 'update_task').
    :param entity_name: The name of the entity being acted on (if known).
    :param args: The tool arguments.
    :returns: Lowercase action description like 'update the due date for "Task"'.
    """
    # Dispatch based on tool name prefix
    if tool_name.startswith("update_"):
        return _format_update_action(entity_name, args)
    if tool_name.startswith("cancel_"):
        return _format_cancel_action(entity_name, args)

    # Fallback for unknown tools
    if entity_name:
        return f'{tool_name.replace("_", " ")} "{entity_name}"'
    return tool_name.replace("_", " ")


def format_confirmation_message(
    tools: list[tuple[PendingToolAction, str | None]],
) -> str:
    """Format a confirmation request message.

    For content field updates, shows a before/after diff (if available).
    For scalar field updates (status, due_date, priority), shows the action only.

    :param tools: List of (PendingToolAction, entity_name) tuples.
    :returns: Human-readable confirmation message.
    """
    if len(tools) == 1:
        tool, entity_name_override = tools[0]
        entity_name = entity_name_override or tool.entity_name
        action = format_action(tool.tool_name, entity_name, tool.input_args)

        # For content updates, show the diff
        if tool.new_content is not None:
            return _format_single_confirmation_with_diff(tool, action)

        return f"I'll {action} - sound good?"

    # Multiple actions
    lines = ["Just confirming these:\n"]

    for tool, entity_name_override in tools:
        entity_name = entity_name_override or tool.entity_name
        action = format_action(tool.tool_name, entity_name, tool.input_args)
        action_capitalised = action[0].upper() + action[1:] if action else action

        if tool.new_content is not None:
            # Content update - show diff inline
            lines.append(f"{tool.index}. {action_capitalised}")
            lines.append(_format_inline_diff(tool.old_content, tool.new_content))
        else:
            lines.append(f"{tool.index}. {action_capitalised}")

    lines.append("\nThis look right?")
    return "\n".join(lines)


def _format_single_confirmation_with_diff(
    tool: PendingToolAction,
    action: str,
) -> str:
    """Format a single action confirmation with diff display.

    Caller must verify tool.new_content is not None before calling.

    :param tool: The pending tool action (must have new_content set).
    :param action: Formatted action description (includes entity name).
    :returns: Confirmation message with diff.
    """
    lines = [f"I'd {action}:\n"]

    if tool.old_content is not None:
        truncated_old = _truncate_content(tool.old_content)
        lines.append(f'**Before:** "{truncated_old}"')
    else:
        lines.append("**Before:** (not available)")

    # Caller guarantees new_content exists (checked before calling)
    new_content = tool.new_content
    if new_content is None:
        raise ValueError("new_content must not be None - caller should check before calling")
    truncated_new = _truncate_content(new_content)
    lines.append(f'**After:** "{truncated_new}"')

    lines.append("\nThis look right?")
    return "\n".join(lines)


def _format_inline_diff(old_content: str | None, new_content: str) -> str:
    """Format an inline diff for batch confirmation display.

    :param old_content: Previous content (may be None).
    :param new_content: New content.
    :returns: Formatted inline diff.
    """
    lines = []
    if old_content is not None:
        truncated_old = _truncate_content(old_content)
        lines.append(f'   **Before:** "{truncated_old}"')
    truncated_new = _truncate_content(new_content)
    lines.append(f'   **After:** "{truncated_new}"')
    return "\n".join(lines)


def _truncate_content(content: str, max_length: int = DIFF_CONTENT_TRUNCATION_LENGTH) -> str:
    """Truncate content if it exceeds max length.

    :param content: Content to potentially truncate.
    :param max_length: Maximum length before truncation.
    :returns: Original or truncated content with ellipsis.
    """
    if len(content) <= max_length:
        return content
    return content[:max_length].strip() + "..."
