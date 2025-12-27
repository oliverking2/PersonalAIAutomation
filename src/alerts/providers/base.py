"""Base protocol for alert providers."""

from typing import Protocol

from src.alerts.enums import AlertType
from src.alerts.models import AlertData


class AlertProvider(Protocol):
    """Protocol for alert data providers.

    Each alert type has a provider that fetches data and converts it
    to AlertData for formatting and sending.
    """

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        ...

    def get_pending_alerts(self) -> list[AlertData]:
        """Fetch alerts that should be sent.

        :returns: List of AlertData objects to send.
        """
        ...

    def mark_sent(self, source_id: str) -> None:
        """Mark an alert source as sent (if applicable).

        :param source_id: The source identifier to mark.
        """
        ...
