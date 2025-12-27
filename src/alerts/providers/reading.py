"""Reading list alert provider for weekly reminders."""

import logging
from datetime import date, timedelta

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.api.client import InternalAPIClient

logger = logging.getLogger(__name__)


class ReadingAlertProvider:
    """Provider for weekly reading list reminders using the internal API."""

    # Number of days after which an item is considered stale
    STALE_DAYS = 30

    def __init__(self, api_client: InternalAPIClient) -> None:
        """Initialise the provider.

        :param api_client: API client for querying reading list.
        """
        self._client = api_client

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.WEEKLY_READING

    def get_pending_alerts(self) -> list[AlertData]:
        """Get reading list summary for weekly reminder.

        Returns a single AlertData with high priority items and stale items.

        :returns: List with single AlertData or empty if no relevant items.
        """
        today = date.today()
        source_id = today.isocalendar()[1]  # Week number
        source_id_str = f"{today.year}-W{source_id:02d}"

        items: list[AlertItem] = []

        # Get high priority items marked "To Read"
        high_priority_response = self._client.post(
            "/notion/reading-list/query",
            json={"priority": "High", "status": "To Read", "include_completed": False},
        )
        high_priority_items = high_priority_response.get("results", [])
        for item in high_priority_items:
            items.append(
                AlertItem(
                    name=item.get("title", "Untitled"),
                    url=item.get("item_url") or item.get("notion_url"),
                    metadata={
                        "section": "high_priority",
                        "item_type": item.get("item_type", ""),
                    },
                )
            )

        # Get stale items (not edited in 30+ days)
        stale_cutoff = today - timedelta(days=self.STALE_DAYS)
        stale_response = self._client.post(
            "/notion/reading-list/query",
            json={
                "edited_before": stale_cutoff.isoformat(),
                "status": "To Read",
                "include_completed": False,
            },
        )
        stale_items = stale_response.get("results", [])
        for item in stale_items:
            # Avoid duplicates from high priority
            if not any(i.name == item.get("title") for i in items):
                items.append(
                    AlertItem(
                        name=item.get("title", "Untitled"),
                        url=item.get("item_url") or item.get("notion_url"),
                        metadata={
                            "section": "stale",
                            "item_type": item.get("item_type", ""),
                        },
                    )
                )

        if not items:
            logger.info("No reading list items for weekly reminder")
            return []

        logger.info(
            f"Reading reminder: {len(high_priority_items)} high priority, "
            f"{len(stale_items)} stale items"
        )

        return [
            AlertData(
                alert_type=AlertType.WEEKLY_READING,
                source_id=source_id_str,
                title="Weekly Reading List Reminder",
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """No-op for scheduled reminders.

        Reading reminders don't have a source record to update.

        :param source_id: The week string (unused).
        """
        pass
