"""Tests for alert database operations."""

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.database.alerts.models import AlertType, SentAlert
from src.database.alerts.operations import (
    create_sent_alert,
    get_recent_alerts,
    get_sent_alerts_by_type,
    was_alert_sent_today,
)


class TestCreateSentAlert(unittest.TestCase):
    """Tests for create_sent_alert operation."""

    def test_creates_alert_with_required_fields(self) -> None:
        """Test creating an alert with required fields only."""
        mock_session = MagicMock()

        alert = create_sent_alert(
            session=mock_session,
            alert_type=AlertType.NEWSLETTER,
            chat_id="123456",
            content="Test newsletter content",
        )

        self.assertEqual(alert.alert_type, AlertType.NEWSLETTER)
        self.assertEqual(alert.chat_id, "123456")
        self.assertEqual(alert.content, "Test newsletter content")
        self.assertIsNone(alert.telegram_message_id)
        self.assertIsNone(alert.source_id)
        mock_session.add.assert_called_once_with(alert)
        mock_session.flush.assert_called_once()

    def test_creates_alert_with_all_fields(self) -> None:
        """Test creating an alert with all fields."""
        mock_session = MagicMock()

        alert = create_sent_alert(
            session=mock_session,
            alert_type=AlertType.DAILY_TASK,
            chat_id="789",
            content="Daily task reminder",
            telegram_message_id=42,
            source_id="2025-01-15",
        )

        self.assertEqual(alert.alert_type, AlertType.DAILY_TASK)
        self.assertEqual(alert.telegram_message_id, 42)
        self.assertEqual(alert.source_id, "2025-01-15")


class TestWasAlertSentToday(unittest.TestCase):
    """Tests for was_alert_sent_today operation."""

    def test_returns_true_when_alert_exists(self) -> None:
        """Test that True is returned when alert was sent today."""
        mock_session = MagicMock()
        mock_alert = SentAlert(
            alert_type=AlertType.NEWSLETTER,
            chat_id="123",
            content="test",
            source_id="abc-123",
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_alert

        result = was_alert_sent_today(
            session=mock_session,
            alert_type=AlertType.NEWSLETTER,
            source_id="abc-123",
        )

        self.assertTrue(result)

    def test_returns_false_when_no_alert_exists(self) -> None:
        """Test that False is returned when no alert was sent today."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = was_alert_sent_today(
            session=mock_session,
            alert_type=AlertType.NEWSLETTER,
            source_id="xyz-789",
        )

        self.assertFalse(result)


class TestGetSentAlertsByType(unittest.TestCase):
    """Tests for get_sent_alerts_by_type operation."""

    def test_returns_alerts_of_specified_type(self) -> None:
        """Test that alerts are filtered by type."""
        mock_session = MagicMock()
        mock_alerts = [
            SentAlert(alert_type=AlertType.DAILY_TASK, chat_id="1", content="task 1"),
            SentAlert(alert_type=AlertType.DAILY_TASK, chat_id="1", content="task 2"),
        ]
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_alerts

        result = get_sent_alerts_by_type(
            session=mock_session,
            alert_type=AlertType.DAILY_TASK,
        )

        self.assertEqual(len(result), 2)

    def test_filters_by_since_datetime(self) -> None:
        """Test that since parameter filters older alerts."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        since = datetime.now(UTC) - timedelta(hours=6)
        result = get_sent_alerts_by_type(
            session=mock_session,
            alert_type=AlertType.NEWSLETTER,
            since=since,
        )

        self.assertEqual(result, [])


class TestGetRecentAlerts(unittest.TestCase):
    """Tests for get_recent_alerts operation."""

    def test_returns_alerts_from_last_24_hours_by_default(self) -> None:
        """Test that default is 24 hours lookback."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = get_recent_alerts(session=mock_session)

        self.assertEqual(result, [])
        mock_session.query.assert_called()

    def test_respects_hours_parameter(self) -> None:
        """Test that hours parameter is used."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = get_recent_alerts(session=mock_session, hours=48)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
