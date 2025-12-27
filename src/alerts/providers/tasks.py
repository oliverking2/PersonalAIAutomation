"""Task alert provider for daily reminders."""

import logging
from datetime import date, timedelta

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.api.client import InternalAPIClient

logger = logging.getLogger(__name__)


class TaskAlertProvider:
    """Provider for daily task reminders using the internal API."""

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying tasks.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.DAILY_TASK

    def get_pending_alerts(self) -> list[AlertData]:
        """Get task summary for daily reminder.

        Returns a single AlertData with overdue tasks, tasks due today,
        and high priority tasks due this week.

        :returns: List with single AlertData or empty if no relevant tasks.
        """
        today = date.today()
        source_id = today.isoformat()

        items: list[AlertItem] = []

        # Get overdue tasks (due before today, not done)
        overdue_response = self._client.post(
            "/notion/tasks/query",
            json={"due_before": today.isoformat(), "include_done": False},
        )
        overdue_tasks = overdue_response.get("results", [])
        for task in overdue_tasks:
            due = task.get("due_date")
            days_overdue = (today - date.fromisoformat(due)).days if due else 0
            items.append(
                AlertItem(
                    name=task.get("task_name", "Untitled"),
                    url=task.get("notion_url"),
                    metadata={"section": "overdue", "days_overdue": str(days_overdue)},
                )
            )

        # Get tasks due today
        today_response = self._client.post(
            "/notion/tasks/query",
            json={"due_date": today.isoformat(), "include_done": False},
        )
        today_tasks = today_response.get("results", [])
        for task in today_tasks:
            items.append(
                AlertItem(
                    name=task.get("task_name", "Untitled"),
                    url=task.get("notion_url"),
                    metadata={"section": "due_today"},
                )
            )

        # Get high priority tasks due this week
        week_end = today + timedelta(days=7)
        high_priority_response = self._client.post(
            "/notion/tasks/query",
            json={
                "due_after": today.isoformat(),
                "due_before": week_end.isoformat(),
                "priority": "High",
                "include_done": False,
            },
        )
        high_priority_tasks = high_priority_response.get("results", [])
        for task in high_priority_tasks:
            items.append(
                AlertItem(
                    name=task.get("task_name", "Untitled"),
                    url=task.get("notion_url"),
                    metadata={
                        "section": "high_priority_week",
                        "due_date": task.get("due_date", ""),
                    },
                )
            )

        if not items:
            logger.info("No tasks for daily reminder")
            return []

        logger.info(
            f"Task reminder: {len(overdue_tasks)} overdue, "
            f"{len(today_tasks)} due today, {len(high_priority_tasks)} high priority"
        )

        return [
            AlertData(
                alert_type=AlertType.DAILY_TASK,
                source_id=source_id,
                title="Daily Task Summary",
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders.

        Task reminders don't have a source record to update.

        :param source_id: The date string (unused).
        """
        pass
