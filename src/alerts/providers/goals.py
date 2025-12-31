"""Goal alert provider for weekly reviews."""

import logging
from datetime import date
from typing import Any, cast

from dateutil.relativedelta import relativedelta

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.api.client import InternalAPIClient
from src.notion.enums import GoalStatus

logger = logging.getLogger(__name__)


class GoalAlertProvider:
    """Provider for weekly goal review reminders using the internal API."""

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying goals.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.WEEKLY_GOAL

    def get_pending_alerts(self) -> list[AlertData]:
        """Get goal summary for weekly review.

        Returns goals that are either in progress or have a due date
        within the next 3 months.

        :returns: List with single AlertData or empty if no relevant goals.
        """
        today = date.today()
        # ISO week format: YYYY-WXX
        source_id = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
        three_months = today + relativedelta(months=3)

        # Get goals in progress
        in_progress_response = cast(
            dict[str, Any],
            self._client.post(
                "/notion/goals/query",
                json={"status": GoalStatus.IN_PROGRESS.value, "include_done": False},
            ),
        )
        in_progress_goals = in_progress_response.get("results", [])

        # Get goals due within 3 months (not done)
        due_soon_response = cast(
            dict[str, Any],
            self._client.post(
                "/notion/goals/query",
                json={"due_before": three_months.isoformat(), "include_done": False},
            ),
        )
        due_soon_goals = due_soon_response.get("results", [])

        # Combine and deduplicate by goal ID
        seen_ids: set[str] = set()
        goals: list[dict[str, Any]] = []

        for goal in in_progress_goals + due_soon_goals:
            goal_id = goal.get("id", "")
            if goal_id not in seen_ids:
                seen_ids.add(goal_id)
                goals.append(goal)

        if not goals:
            logger.info("No relevant goals for weekly review")
            return []

        items: list[AlertItem] = []
        for goal in goals:
            progress = goal.get("progress") or 0
            status = goal.get("status", "")
            due_date = goal.get("due_date", "")

            items.append(
                AlertItem(
                    name=goal.get("goal_name", "Untitled"),
                    url=None,
                    metadata={
                        "progress": str(int(progress)),
                        "status": status,
                        "due_date": due_date,
                    },
                )
            )

        logger.info(f"Goal review: {len(goals)} relevant goals")

        return [
            AlertData(
                alert_type=AlertType.WEEKLY_GOAL,
                source_id=source_id,
                title="Weekly Goal Review",
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders.

        Goal reviews don't have a source record to update.

        :param source_id: The week string (unused).
        """
        pass
