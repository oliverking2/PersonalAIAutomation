"""Tests for AlertService."""

import unittest
from unittest.mock import MagicMock, patch

from src.alerts.enums import AlertType
from src.alerts.models import AlertData
from src.alerts.service import AlertService
from src.telegram.client import TelegramClientError
from src.telegram.models import SendMessageResult


class TestAlertService(unittest.TestCase):
    """Tests for AlertService."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.mock_telegram = MagicMock()
        self.mock_telegram.send_message_sync.return_value = SendMessageResult(
            message_id=123, chat_id=456
        )

        self.mock_provider = MagicMock()
        self.mock_provider.alert_type = AlertType.NEWSLETTER
        self.mock_provider.get_pending_alerts.return_value = [
            AlertData(
                alert_type=AlertType.NEWSLETTER,
                source_id="test-123",
                title="Test Newsletter",
                items=[],
            )
        ]

    @patch("src.alerts.service.was_alert_sent_today")
    @patch("src.alerts.service.create_sent_alert")
    def test_sends_and_tracks_alert(self, mock_create: MagicMock, mock_was_sent: MagicMock) -> None:
        """Test that alerts are sent and tracked."""
        mock_was_sent.return_value = False

        service = AlertService(
            session=self.mock_session,
            telegram_client=self.mock_telegram,
            providers=[self.mock_provider],
        )

        result = service.send_alerts()

        self.assertEqual(result.alerts_sent, 1)
        self.assertEqual(result.alerts_skipped, 0)
        self.assertEqual(len(result.errors), 0)
        self.mock_telegram.send_message_sync.assert_called_once()
        mock_create.assert_called_once()
        self.mock_provider.mark_sent.assert_called_once_with("test-123")

    @patch("src.alerts.service.was_alert_sent_today")
    def test_skips_already_sent_today(self, mock_was_sent: MagicMock) -> None:
        """Test that alerts already sent today are skipped."""
        mock_was_sent.return_value = True

        service = AlertService(
            session=self.mock_session,
            telegram_client=self.mock_telegram,
            providers=[self.mock_provider],
        )

        result = service.send_alerts()

        self.assertEqual(result.alerts_sent, 0)
        self.assertEqual(result.alerts_skipped, 1)
        self.mock_telegram.send_message_sync.assert_not_called()

    @patch("src.alerts.service.was_alert_sent_today")
    def test_handles_send_failure(self, mock_was_sent: MagicMock) -> None:
        """Test that send failures are recorded as errors."""
        mock_was_sent.return_value = False
        self.mock_telegram.send_message_sync.side_effect = TelegramClientError("Failed")

        service = AlertService(
            session=self.mock_session,
            telegram_client=self.mock_telegram,
            providers=[self.mock_provider],
        )

        result = service.send_alerts()

        self.assertEqual(result.alerts_sent, 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Failed", result.errors[0])

    def test_skips_when_no_pending_alerts(self) -> None:
        """Test that empty provider returns empty result."""
        self.mock_provider.get_pending_alerts.return_value = []

        service = AlertService(
            session=self.mock_session,
            telegram_client=self.mock_telegram,
            providers=[self.mock_provider],
        )

        result = service.send_alerts()

        self.assertEqual(result.alerts_sent, 0)
        self.assertEqual(result.alerts_skipped, 0)
        self.assertEqual(len(result.errors), 0)

    @patch("src.alerts.service.was_alert_sent_today")
    @patch("src.alerts.service.create_sent_alert")
    def test_filters_by_alert_type(self, mock_create: MagicMock, mock_was_sent: MagicMock) -> None:
        """Test that alert_types parameter filters providers."""
        mock_was_sent.return_value = False

        task_provider = MagicMock()
        task_provider.alert_type = AlertType.DAILY_TASK_WORK
        task_provider.get_pending_alerts.return_value = []

        service = AlertService(
            session=self.mock_session,
            telegram_client=self.mock_telegram,
            providers=[self.mock_provider, task_provider],
        )

        result = service.send_alerts(alert_types=[AlertType.NEWSLETTER])

        self.assertEqual(result.alerts_sent, 1)
        # Newsletter provider was called, task provider was not
        self.mock_provider.get_pending_alerts.assert_called_once()
        task_provider.get_pending_alerts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
