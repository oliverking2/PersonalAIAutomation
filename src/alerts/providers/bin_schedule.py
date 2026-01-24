"""Bin schedule alert provider for weekly bin collection reminders."""

import logging
import os
from datetime import date
from enum import StrEnum

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.alerts.providers.base import AlertProvider

logger = logging.getLogger(__name__)


class BinType(StrEnum):
    """Types of bins for collection."""

    GENERAL_WASTE = "General Waste"
    RECYCLING = "Recycling"


class BinScheduleAlertProvider(AlertProvider):
    """Provider for weekly bin collection reminders.

    Calculates which bin to put out based on alternating weeks from a reference date.
    The reference date should be a Sunday when General Waste is collected the next day.

    Configuration via environment variable:
        BIN_REFERENCE_DATE: A known "General Waste" Sunday in YYYY-MM-DD format
    """

    def __init__(self) -> None:
        """Initialise the provider.

        :raises ValueError: If BIN_REFERENCE_DATE is not set.
        """
        reference_str = os.environ.get("BIN_REFERENCE_DATE")
        if not reference_str:
            raise ValueError(
                "BIN_REFERENCE_DATE environment variable is not set. "
                "Set it to a Sunday when General Waste is collected (YYYY-MM-DD format)."
            )

        try:
            self._reference_date = date.fromisoformat(reference_str)
        except ValueError as e:
            raise ValueError(
                f"BIN_REFERENCE_DATE '{reference_str}' is not a valid date. Use YYYY-MM-DD format."
            ) from e

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.BIN_SCHEDULE

    def get_current_bin_type(self, today: date | None = None) -> BinType:
        """Calculate which bin should be put out.

        Uses the reference date to determine the alternating pattern:
        - Week 0 (reference week and even weeks): General Waste
        - Week 1 (odd weeks): Recycling

        :param today: The date to calculate for (defaults to today).
        :returns: The type of bin to put out.
        """
        if today is None:
            today = date.today()

        # Calculate weeks elapsed since reference date
        days_elapsed = (today - self._reference_date).days
        weeks_elapsed = days_elapsed // 7

        # Even weeks (including reference week 0) = General Waste
        # Odd weeks = Recycling
        if weeks_elapsed % 2 == 0:
            return BinType.GENERAL_WASTE
        return BinType.RECYCLING

    def get_pending_alerts(self) -> list[AlertData]:
        """Get bin reminder alert for the current week.

        :returns: List with single AlertData containing bin type.
        """
        today = date.today()
        bin_type = self.get_current_bin_type(today)

        # Use ISO week format as source_id: YYYY-WXX
        source_id = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"

        logger.info(f"Bin reminder: {bin_type.value} for week {source_id}")

        return [
            AlertData(
                alert_type=AlertType.BIN_SCHEDULE,
                source_id=source_id,
                title="Bin Reminder",
                items=[
                    AlertItem(
                        name=bin_type.value,
                        url=None,
                        metadata={"bin_type": bin_type.value},
                    )
                ],
            )
        ]
