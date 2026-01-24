"""Tests for BinScheduleAlertProvider."""

import os
import unittest
from datetime import date
from unittest.mock import patch

from src.alerts.enums import AlertType
from src.alerts.providers.bin_schedule import BinScheduleAlertProvider, BinType


class TestBinScheduleAlertProvider(unittest.TestCase):
    """Tests for BinScheduleAlertProvider."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Reference date: Sunday 26 Jan 2026 (General Waste week)
        self.reference_date = "2026-01-26"

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_alert_type(self) -> None:
        """Test that alert_type returns BIN_SCHEDULE."""
        provider = BinScheduleAlertProvider()
        self.assertEqual(provider.alert_type, AlertType.BIN_SCHEDULE)

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_reference_date_returns_general_waste(self) -> None:
        """Test that the reference date itself returns General Waste."""
        provider = BinScheduleAlertProvider()
        reference = date(2026, 1, 26)

        bin_type = provider.get_current_bin_type(reference)

        self.assertEqual(bin_type, BinType.GENERAL_WASTE)

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_one_week_later_returns_recycling(self) -> None:
        """Test that one week after reference returns Recycling."""
        provider = BinScheduleAlertProvider()
        one_week_later = date(2026, 2, 2)  # Feb 2, 2026

        bin_type = provider.get_current_bin_type(one_week_later)

        self.assertEqual(bin_type, BinType.RECYCLING)

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_two_weeks_later_returns_general_waste(self) -> None:
        """Test that two weeks after reference returns General Waste."""
        provider = BinScheduleAlertProvider()
        two_weeks_later = date(2026, 2, 9)  # Feb 9, 2026

        bin_type = provider.get_current_bin_type(two_weeks_later)

        self.assertEqual(bin_type, BinType.GENERAL_WASTE)

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_three_weeks_later_returns_recycling(self) -> None:
        """Test that three weeks after reference returns Recycling."""
        provider = BinScheduleAlertProvider()
        three_weeks_later = date(2026, 2, 16)  # Feb 16, 2026

        bin_type = provider.get_current_bin_type(three_weeks_later)

        self.assertEqual(bin_type, BinType.RECYCLING)

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_mid_week_uses_week_number(self) -> None:
        """Test that mid-week dates use the correct week calculation."""
        provider = BinScheduleAlertProvider()
        # Wednesday of reference week (Jan 28, 2026)
        mid_reference_week = date(2026, 1, 28)
        # Wednesday one week later (Feb 4, 2026)
        mid_next_week = date(2026, 2, 4)

        self.assertEqual(provider.get_current_bin_type(mid_reference_week), BinType.GENERAL_WASTE)
        self.assertEqual(provider.get_current_bin_type(mid_next_week), BinType.RECYCLING)

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_get_pending_alerts_returns_alert_data(self) -> None:
        """Test that get_pending_alerts returns correct AlertData."""
        provider = BinScheduleAlertProvider()

        with (
            patch.object(provider, "get_current_bin_type", return_value=BinType.RECYCLING),
            patch("src.alerts.providers.bin_schedule.date") as mock_date,
        ):
            mock_date.today.return_value = date(2026, 2, 1)
            mock_date.fromisoformat = date.fromisoformat
            alerts = provider.get_pending_alerts()

        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.alert_type, AlertType.BIN_SCHEDULE)
        self.assertEqual(alert.title, "Bin Reminder")
        self.assertEqual(len(alert.items), 1)
        self.assertEqual(alert.items[0].name, "Recycling")
        self.assertEqual(alert.items[0].metadata["bin_type"], "Recycling")

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_source_id_uses_iso_week_format(self) -> None:
        """Test that source_id uses ISO week format YYYY-WXX."""
        provider = BinScheduleAlertProvider()

        with patch("src.alerts.providers.bin_schedule.date") as mock_date:
            # Feb 1, 2026 is in ISO week 5
            mock_date.today.return_value = date(2026, 2, 1)
            mock_date.fromisoformat = date.fromisoformat
            alerts = provider.get_pending_alerts()

        self.assertEqual(alerts[0].source_id, "2026-W05")

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "2026-01-26"})
    def test_mark_sent_is_noop(self) -> None:
        """Test that mark_sent does nothing (stateless)."""
        provider = BinScheduleAlertProvider()

        # Should not raise
        provider.mark_sent("2026-W05")

    def test_raises_if_env_not_set(self) -> None:
        """Test that ValueError is raised if BIN_REFERENCE_DATE not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if it exists
            os.environ.pop("BIN_REFERENCE_DATE", None)

            with self.assertRaises(ValueError) as ctx:
                BinScheduleAlertProvider()

            self.assertIn("BIN_REFERENCE_DATE", str(ctx.exception))
            self.assertIn("not set", str(ctx.exception))

    @patch.dict(os.environ, {"BIN_REFERENCE_DATE": "invalid-date"})
    def test_raises_if_invalid_date_format(self) -> None:
        """Test that ValueError is raised for invalid date format."""
        with self.assertRaises(ValueError) as ctx:
            BinScheduleAlertProvider()

        self.assertIn("not a valid date", str(ctx.exception))
        self.assertIn("YYYY-MM-DD", str(ctx.exception))


class TestBinType(unittest.TestCase):
    """Tests for BinType enum."""

    def test_general_waste_value(self) -> None:
        """Test General Waste enum value."""
        self.assertEqual(BinType.GENERAL_WASTE.value, "General Waste")

    def test_recycling_value(self) -> None:
        """Test Recycling enum value."""
        self.assertEqual(BinType.RECYCLING.value, "Recycling")


if __name__ == "__main__":
    unittest.main()
