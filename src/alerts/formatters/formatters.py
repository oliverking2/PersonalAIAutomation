"""Alert formatters for converting AlertData to Telegram messages."""

from urllib.parse import urlparse

from src.alerts.enums import AlertType
from src.alerts.formatters.summariser import summarise_description
from src.alerts.models import AlertData


def format_newsletter_alert(alert: AlertData) -> str:
    """Format a newsletter alert as HTML for Telegram.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    """
    lines = [f"<b>{alert.title}</b>", ""]

    for item in alert.items:
        lines.append(f"<b>{item.name}</b>")
        description = item.metadata.get("description", "")
        if description:
            lines.append(summarise_description(description, max_length=150))
        if item.url:
            domain = urlparse(item.url).netloc
            lines.append(f'<a href="{item.url}">{domain}</a>')
        lines.append("")

    return "\n".join(lines).strip()


def format_task_alert(alert: AlertData) -> str:
    """Format a daily task reminder alert as HTML.

    Organises tasks into sections: overdue, due today, high priority.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    """
    overdue = [i for i in alert.items if i.metadata.get("section") == "overdue"]
    due_today = [i for i in alert.items if i.metadata.get("section") == "due_today"]
    high_priority = [i for i in alert.items if i.metadata.get("section") == "high_priority_week"]

    lines = [f"<b>{alert.title}</b>", ""]

    if overdue:
        lines.append(f"<b>OVERDUE ({len(overdue)})</b>")
        for item in overdue:
            days = item.metadata.get("days_overdue", "?")
            lines.append(f"  - {item.name} ({days} days overdue)")
        lines.append("")

    if due_today:
        lines.append(f"<b>DUE TODAY ({len(due_today)})</b>")
        for item in due_today:
            lines.append(f"  - {item.name}")
        lines.append("")

    if high_priority:
        lines.append(f"<b>HIGH PRIORITY THIS WEEK ({len(high_priority)})</b>")
        for item in high_priority:
            due = item.metadata.get("due_date", "")
            due_str = f" (Due: {due})" if due else ""
            lines.append(f"  - {item.name}{due_str}")
        lines.append("")

    return "\n".join(lines).strip()


def format_goal_alert(alert: AlertData) -> str:
    """Format a monthly goal review alert as HTML.

    Shows progress bars and status for each goal.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    """
    lines = [f"<b>{alert.title}</b>", ""]

    # Separate by status
    in_progress = [i for i in alert.items if i.metadata.get("status") == "In progress"]
    not_started = [i for i in alert.items if i.metadata.get("status") == "Not started"]

    if in_progress:
        lines.append(f"<b>IN PROGRESS ({len(in_progress)})</b>")
        for item in in_progress:
            progress = int(item.metadata.get("progress", 0))
            bar = _progress_bar(progress)
            due = item.metadata.get("due_date", "")
            due_str = f"\n  Due: {due}" if due else ""
            lines.append(f"  - {item.name} {bar} {progress}%{due_str}")
        lines.append("")

    if not_started:
        lines.append(f"<b>NOT STARTED ({len(not_started)})</b>")
        for item in not_started:
            lines.append(f"  - {item.name}")
        lines.append("")

    return "\n".join(lines).strip()


def _progress_bar(progress: int, width: int = 10) -> str:
    """Create a text-based progress bar.

    :param progress: Progress percentage (0-100).
    :param width: Number of characters in the bar.
    :returns: Progress bar string like "━━━━░░░░░░".
    """
    filled = int((progress / 100) * width)
    empty = width - filled
    return "━" * filled + "░" * empty


def format_reading_alert(alert: AlertData) -> str:
    """Format a weekly reading list reminder as HTML.

    Shows high priority and stale items.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    """
    high_priority = [i for i in alert.items if i.metadata.get("section") == "high_priority"]
    stale = [i for i in alert.items if i.metadata.get("section") == "stale"]

    lines = [f"<b>{alert.title}</b>", ""]

    if high_priority:
        lines.append(f"<b>HIGH PRIORITY ({len(high_priority)})</b>")
        for item in high_priority:
            item_type = item.metadata.get("item_type", "")
            type_str = f" [{item_type}]" if item_type else ""
            lines.append(f"  - {item.name}{type_str}")
        lines.append("")

    if stale:
        lines.append(f"<b>GETTING STALE ({len(stale)})</b>")
        for item in stale:
            item_type = item.metadata.get("item_type", "")
            type_str = f" [{item_type}]" if item_type else ""
            lines.append(f"  - {item.name}{type_str}")
        lines.append("")

    return "\n".join(lines).strip()


def format_alert(alert: AlertData) -> str:
    """Format any alert based on its type.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    :raises ValueError: If alert type is unknown.
    """
    formatters = {
        AlertType.NEWSLETTER: format_newsletter_alert,
        AlertType.DAILY_TASK: format_task_alert,
        AlertType.MONTHLY_GOAL: format_goal_alert,
        AlertType.WEEKLY_READING: format_reading_alert,
    }

    formatter = formatters.get(alert.alert_type)
    if formatter is None:
        raise ValueError(f"Unknown alert type: {alert.alert_type}")

    return formatter(alert)
