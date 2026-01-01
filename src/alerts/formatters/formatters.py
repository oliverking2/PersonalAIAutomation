"""Alert formatters for converting AlertData to Telegram messages."""

from urllib.parse import urlparse

from src.alerts.enums import AlertType
from src.alerts.formatters.summariser import summarise_description
from src.alerts.models import AlertData, AlertItem


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


def _format_task_section(
    items: list[AlertItem],
    header: str,
    include_due_date: bool = False,
    include_days_overdue: bool = False,
) -> list[str]:
    """Format a section of tasks for an alert.

    :param items: List of alert items to format.
    :param header: Section header text.
    :param include_due_date: Whether to include due date in output.
    :param include_days_overdue: Whether to include days overdue in output.
    :returns: List of formatted lines.
    """
    if not items:
        return []

    lines = [f"<b>{header} ({len(items)})</b>"]
    for item in items:
        suffix = ""
        if include_days_overdue:
            days = item.metadata.get("days_overdue", "?")
            suffix = f" ({days} days)"
        elif include_due_date:
            due = item.metadata.get("due_date", "")
            suffix = f" (Due: {due})" if due else ""
        lines.append(f"  • {item.name}{suffix}")
    lines.append("")
    return lines


def format_task_alert(alert: AlertData) -> str:
    """Format a task reminder alert as HTML.

    Organises tasks into sections based on their metadata.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    """
    # Group items by section
    sections: dict[str, list[AlertItem]] = {}
    for item in alert.items:
        section = item.metadata.get("section", "unknown")
        sections.setdefault(section, []).append(item)

    lines = [f"<b>{alert.title}</b>", ""]

    # Format each section in order
    lines.extend(
        _format_task_section(sections.get("overdue", []), "OVERDUE", include_days_overdue=True)
    )
    lines.extend(_format_task_section(sections.get("incomplete_today", []), "INCOMPLETE TODAY"))
    lines.extend(_format_task_section(sections.get("due_today", []), "DUE TODAY"))
    lines.extend(
        _format_task_section(
            sections.get("high_priority_week", []), "HIGH PRIORITY THIS WEEK", include_due_date=True
        )
    )
    lines.extend(
        _format_task_section(
            sections.get("medium_priority_week", []),
            "MEDIUM PRIORITY THIS WEEK",
            include_due_date=True,
        )
    )
    lines.extend(
        _format_task_section(
            sections.get("high_priority_weekend", []),
            "HIGH PRIORITY THIS WEEKEND",
            include_due_date=True,
        )
    )
    lines.extend(
        _format_task_section(
            sections.get("medium_priority_weekend", []),
            "MEDIUM PRIORITY THIS WEEKEND",
            include_due_date=True,
        )
    )

    return "\n".join(lines).strip()


def format_goal_alert(alert: AlertData) -> str:
    """Format a goal review alert as HTML.

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
            lines.append(f"  • {item.name} {bar} {progress}%{due_str}")
        lines.append("")

    if not_started:
        lines.append(f"<b>NOT STARTED ({len(not_started)})</b>")
        for item in not_started:
            lines.append(f"  • {item.name}")
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
            lines.append(f"  • {item.name}{type_str}")
        lines.append("")

    if stale:
        lines.append(f"<b>GETTING STALE ({len(stale)})</b>")
        for item in stale:
            item_type = item.metadata.get("item_type", "")
            type_str = f" [{item_type}]" if item_type else ""
            lines.append(f"  • {item.name}{type_str}")
        lines.append("")

    return "\n".join(lines).strip()


def format_substack_alert(alert: AlertData) -> str:
    """Format a Substack posts alert as HTML for Telegram.

    Each alert contains posts from a single publication.
    Format: Publication name as title, then each post with link + subtitle.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    """
    lines = [f"<b>{alert.title}</b>", ""]

    for item in alert.items:
        # Title as link, with (Paid) indicator for paywalled posts
        is_paywalled = item.metadata.get("is_paywalled") == "true"
        paid_suffix = " (Paid)" if is_paywalled else ""
        if item.url:
            lines.append(f'<a href="{item.url}">{item.name}</a>{paid_suffix}')
        else:
            lines.append(f"<b>{item.name}</b>{paid_suffix}")

        # Subtitle if present
        subtitle = item.metadata.get("subtitle", "")
        if subtitle:
            lines.append(f"<i>{subtitle}</i>")

        lines.append("")

    return "\n".join(lines).strip()


def format_medium_alert(alert: AlertData) -> str:
    """Format a Medium digest alert as HTML for Telegram.

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


def format_alert(alert: AlertData) -> str:
    """Format any alert based on its type.

    :param alert: The alert data to format.
    :returns: HTML-formatted message string.
    :raises ValueError: If alert type is unknown.
    """
    formatters = {
        AlertType.NEWSLETTER: format_newsletter_alert,
        AlertType.MEDIUM: format_medium_alert,
        AlertType.DAILY_TASK_WORK: format_task_alert,
        AlertType.DAILY_TASK_PERSONAL: format_task_alert,
        AlertType.DAILY_TASK_OVERDUE: format_task_alert,
        AlertType.WEEKLY_GOAL: format_goal_alert,
        AlertType.WEEKLY_READING: format_reading_alert,
        AlertType.SUBSTACK: format_substack_alert,
    }

    formatter = formatters.get(alert.alert_type)
    if formatter is None:
        raise ValueError(f"Unknown alert type: {alert.alert_type}")

    return formatter(alert)
