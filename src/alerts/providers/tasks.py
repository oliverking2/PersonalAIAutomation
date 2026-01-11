"""Task alert providers for daily reminders."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, cast

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.api.client import InternalAPIClient
from src.notion.enums import Priority, TaskGroup

logger = logging.getLogger(__name__)

# Monday = 0, Saturday = 5, Sunday = 6
MONDAY = 0
SATURDAY = 5


@dataclass
class TaskQueryParams:
    """Parameters for querying tasks from the API."""

    due_date: date | None = None
    due_before: date | None = None
    due_after: date | None = None
    priority: Priority | None = None
    task_groups: list[TaskGroup] | None = None


def _query_tasks(client: InternalAPIClient, params: TaskQueryParams) -> list[dict[str, Any]]:
    """Query tasks from the API with the given filters.

    :param client: API client for querying tasks.
    :param params: Query parameters.
    :returns: List of task dictionaries.
    """
    results: list[dict[str, Any]] = []

    groups = params.task_groups or [None]  # type: ignore[list-item]
    for group in groups:
        payload: dict[str, Any] = {"include_done": False}
        if params.due_date:
            payload["due_date"] = params.due_date.isoformat()
        if params.due_before:
            payload["due_before"] = params.due_before.isoformat()
        if params.due_after:
            payload["due_after"] = params.due_after.isoformat()
        if params.priority:
            payload["priority"] = params.priority.value
        if group:
            payload["task_group"] = group.value

        response = cast(
            dict[str, Any],
            client.post("/notion/tasks/query", json=payload),
        )
        results.extend(response.get("results", []))

    return results


def _create_alert_item(task: dict[str, Any], section: str, today: date) -> AlertItem:
    """Create an AlertItem from a task dictionary.

    :param task: Task data from the API.
    :param section: Section identifier for the item.
    :param today: Today's date for calculating days overdue.
    :returns: AlertItem with appropriate metadata.
    """
    metadata: dict[str, str] = {"section": section}

    due = task.get("due_date")
    if section == "overdue" and due:
        days_overdue = (today - date.fromisoformat(due)).days
        metadata["days_overdue"] = str(days_overdue)
    elif due:
        metadata["due_date"] = due

    return AlertItem(
        name=task.get("task_name", "Untitled"),
        url=None,
        metadata=metadata,
    )


class WorkTaskAlertProvider:
    """Provider for daily work task reminders.

    Sends work tasks due today. On Mondays, also includes high priority
    and medium priority work tasks for the week.
    """

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying tasks.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.DAILY_TASK_WORK

    def get_pending_alerts(self) -> list[AlertData]:
        """Get work task summary for daily reminder.

        Includes overdue tasks and tasks due today as a morning digest.

        :returns: List with single AlertData or empty if no relevant tasks.
        """
        today = date.today()
        source_id = f"{today.isoformat()}-work"
        is_monday = today.weekday() == MONDAY

        items: list[AlertItem] = []
        work_groups = [TaskGroup.WORK]

        # Get overdue work tasks (due before today, not done)
        overdue_tasks = _query_tasks(
            self._client,
            TaskQueryParams(due_before=today, task_groups=work_groups),
        )
        for task in overdue_tasks:
            items.append(_create_alert_item(task, "overdue", today))

        # Get work tasks due today
        due_today_tasks = _query_tasks(
            self._client,
            TaskQueryParams(due_date=today, task_groups=work_groups),
        )
        for task in due_today_tasks:
            items.append(_create_alert_item(task, "due_today", today))

        # On Monday, include weekly info
        high_priority_count = 0
        medium_priority_count = 0
        if is_monday:
            week_end = today + timedelta(days=5)  # Mon-Fri

            # High priority work tasks (not due today to avoid duplicates)
            high_priority_tasks = _query_tasks(
                self._client,
                TaskQueryParams(
                    due_after=today,
                    due_before=week_end,
                    priority=Priority.HIGH,
                    task_groups=work_groups,
                ),
            )
            for task in high_priority_tasks:
                items.append(_create_alert_item(task, "high_priority_week", today))
            high_priority_count = len(high_priority_tasks)

            # Medium priority work tasks for the week
            medium_priority_tasks = _query_tasks(
                self._client,
                TaskQueryParams(
                    due_after=today,
                    due_before=week_end,
                    priority=Priority.MEDIUM,
                    task_groups=work_groups,
                ),
            )
            for task in medium_priority_tasks:
                items.append(_create_alert_item(task, "medium_priority_week", today))
            medium_priority_count = len(medium_priority_tasks)

        if not items:
            logger.info("No work tasks for daily reminder")
            return []

        log_parts = []
        if overdue_tasks:
            log_parts.append(f"{len(overdue_tasks)} overdue")
        log_parts.append(f"{len(due_today_tasks)} due today")
        if is_monday:
            log_parts.append(f"{high_priority_count} high priority")
            log_parts.append(f"{medium_priority_count} medium priority this week")
        logger.info(f"Work task reminder: {', '.join(log_parts)}")

        title = "Work Tasks" if not is_monday else "Work Tasks (Weekly Overview)"
        return [
            AlertData(
                alert_type=AlertType.DAILY_TASK_WORK,
                source_id=source_id,
                title=title,
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders."""
        pass


class PersonalTaskAlertProvider:
    """Provider for daily personal task reminders.

    Sends personal and photography tasks due today. On Saturdays, also
    includes high priority and medium priority personal tasks for the weekend.
    """

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying tasks.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.DAILY_TASK_PERSONAL

    def get_pending_alerts(self) -> list[AlertData]:
        """Get personal task summary for daily reminder.

        Includes overdue tasks and tasks due today as a morning digest.

        :returns: List with single AlertData or empty if no relevant tasks.
        """
        today = date.today()
        source_id = f"{today.isoformat()}-personal"
        is_saturday = today.weekday() == SATURDAY

        items: list[AlertItem] = []
        personal_groups = [TaskGroup.PERSONAL, TaskGroup.PHOTOGRAPHY]

        # Get overdue personal/photography tasks (due before today, not done)
        overdue_tasks = _query_tasks(
            self._client,
            TaskQueryParams(due_before=today, task_groups=personal_groups),
        )
        for task in overdue_tasks:
            items.append(_create_alert_item(task, "overdue", today))

        # Get personal/photography tasks due today
        due_today_tasks = _query_tasks(
            self._client,
            TaskQueryParams(due_date=today, task_groups=personal_groups),
        )
        for task in due_today_tasks:
            items.append(_create_alert_item(task, "due_today", today))

        # On Saturday, include weekend info
        high_priority_count = 0
        medium_priority_count = 0
        if is_saturday:
            weekend_end = today + timedelta(days=2)  # Sat-Sun

            # High priority personal tasks (not due today to avoid duplicates)
            high_priority_tasks = _query_tasks(
                self._client,
                TaskQueryParams(
                    due_after=today,
                    due_before=weekend_end,
                    priority=Priority.HIGH,
                    task_groups=personal_groups,
                ),
            )
            for task in high_priority_tasks:
                items.append(_create_alert_item(task, "high_priority_weekend", today))
            high_priority_count = len(high_priority_tasks)

            # Medium priority personal tasks for the weekend
            medium_priority_tasks = _query_tasks(
                self._client,
                TaskQueryParams(
                    due_after=today,
                    due_before=weekend_end,
                    priority=Priority.MEDIUM,
                    task_groups=personal_groups,
                ),
            )
            for task in medium_priority_tasks:
                items.append(_create_alert_item(task, "medium_priority_weekend", today))
            medium_priority_count = len(medium_priority_tasks)

        if not items:
            logger.info("No personal tasks for daily reminder")
            return []

        log_parts = []
        if overdue_tasks:
            log_parts.append(f"{len(overdue_tasks)} overdue")
        log_parts.append(f"{len(due_today_tasks)} due today")
        if is_saturday:
            log_parts.append(f"{high_priority_count} high priority")
            log_parts.append(f"{medium_priority_count} medium priority this weekend")
        logger.info(f"Personal task reminder: {', '.join(log_parts)}")

        title = "Personal Tasks" if not is_saturday else "Personal Tasks (Weekend Overview)"
        return [
            AlertData(
                alert_type=AlertType.DAILY_TASK_PERSONAL,
                source_id=source_id,
                title=title,
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders."""
        pass


class OverdueTaskAlertProvider:
    """Provider for daily overdue task reminders.

    Sends all tasks due today that are not completed, plus all overdue tasks.
    """

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying tasks.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.DAILY_TASK_OVERDUE

    def get_pending_alerts(self) -> list[AlertData]:
        """Get overdue and incomplete task summary.

        :returns: List with single AlertData or empty if no relevant tasks.
        """
        today = date.today()
        source_id = f"{today.isoformat()}-overdue"

        items: list[AlertItem] = []

        # Get overdue tasks (due before today, not done)
        overdue_tasks = _query_tasks(
            self._client,
            TaskQueryParams(due_before=today),
        )
        for task in overdue_tasks:
            items.append(_create_alert_item(task, "overdue", today))

        # Get tasks due today that are not done
        due_today_tasks = _query_tasks(
            self._client,
            TaskQueryParams(due_date=today),
        )
        for task in due_today_tasks:
            items.append(_create_alert_item(task, "incomplete_today", today))

        if not items:
            logger.info("No overdue or incomplete tasks")
            return []

        logger.info(
            f"Overdue task reminder: {len(overdue_tasks)} overdue, "
            f"{len(due_today_tasks)} incomplete today"
        )

        return [
            AlertData(
                alert_type=AlertType.DAILY_TASK_OVERDUE,
                source_id=source_id,
                title="Incomplete & Overdue Tasks",
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders."""
        pass
