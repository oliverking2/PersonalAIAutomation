"""Goal alert provider for monthly reviews."""

import logging
from datetime import date

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.api.client import InternalAPIClient

logger = logging.getLogger(__name__)


class GoalAlertProvider:
    """Provider for monthly goal review reminders using the internal API."""

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying goals.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.MONTHLY_GOAL

    def get_pending_alerts(self) -> list[AlertData]:
        """Get goal summary for monthly review.

        Returns a single AlertData with all in-progress goals
        and their progress.

        :returns: List with single AlertData or empty if no active goals.
        """
        today = date.today()
        source_id = today.strftime("%Y-%m")

        # Get all non-done goals
        response = self._client.post(
            "/notion/goals/query",
            json={"include_done": False, "limit": 100},
        )
        goals = response.get("results", [])

        if not goals:
            logger.info("No active goals for monthly review")
            return []

        items: list[AlertItem] = []
        for goal in goals:
            progress = goal.get("progress") or 0
            status = goal.get("status", "")
            due_date = goal.get("due_date", "")

            items.append(
                AlertItem(
                    name=goal.get("goal_name", "Untitled"),
                    url=goal.get("notion_url"),
                    metadata={
                        "progress": str(int(progress)),
                        "status": status,
                        "due_date": due_date,
                    },
                )
            )

        logger.info(f"Goal review: {len(goals)} active goals")

        month_name = today.strftime("%B %Y")
        return [
            AlertData(
                alert_type=AlertType.MONTHLY_GOAL,
                source_id=source_id,
                title=f"Monthly Goal Review - {month_name}",
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders.

        Goal reviews don't have a source record to update.

        :param source_id: The month string (unused).
        """
        pass
