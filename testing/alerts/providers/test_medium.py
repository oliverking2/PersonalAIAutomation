"""Tests for MediumAlertProvider."""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from src.alerts.enums import AlertType
from src.alerts.providers.medium import MediumAlertProvider


class TestMediumAlertProvider(unittest.TestCase):
    """Tests for MediumAlertProvider."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()

    def test_alert_type(self) -> None:
        """Test that alert_type returns MEDIUM."""
        provider = MediumAlertProvider(session=self.mock_session)
        self.assertEqual(provider.alert_type, AlertType.MEDIUM)

    @patch("src.alerts.base.provider.get_unsent_by_alerted_at")
    def test_get_pending_alerts_converts_digests(self, mock_get_unsent: MagicMock) -> None:
        """Test that digests are converted to AlertData."""
        mock_digest = MagicMock()
        mock_digest.id = uuid.uuid4()
        mock_digest.subject = "Medium Daily Digest"
        mock_digest.articles = []
        mock_get_unsent.return_value = [mock_digest]

        provider = MediumAlertProvider(session=self.mock_session)
        alerts = provider.get_pending_alerts()

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, AlertType.MEDIUM)
        self.assertEqual(alerts[0].source_id, str(mock_digest.id))
        self.assertIn("Medium Digest", alerts[0].title)
        self.assertIn("Medium Daily Digest", alerts[0].title)

    @patch("src.alerts.base.provider.get_unsent_by_alerted_at")
    def test_get_pending_alerts_includes_articles(self, mock_get_unsent: MagicMock) -> None:
        """Test that articles are included as items."""
        mock_article = MagicMock()
        mock_article.title = "Test Article (5 min read)"
        mock_article.url = "https://medium.com/@author/test-article"
        mock_article.description = "Article description"

        mock_digest = MagicMock()
        mock_digest.id = uuid.uuid4()
        mock_digest.subject = "Test"
        mock_digest.articles = [mock_article]
        mock_get_unsent.return_value = [mock_digest]

        provider = MediumAlertProvider(session=self.mock_session)
        alerts = provider.get_pending_alerts()

        self.assertEqual(len(alerts[0].items), 1)
        self.assertEqual(alerts[0].items[0].name, "Test Article (5 min read)")
        self.assertEqual(alerts[0].items[0].url, "https://medium.com/@author/test-article")
        self.assertEqual(alerts[0].items[0].metadata["description"], "Article description")

    @patch("src.alerts.base.provider.get_unsent_by_alerted_at")
    def test_get_pending_alerts_handles_empty_description(self, mock_get_unsent: MagicMock) -> None:
        """Test that empty descriptions are handled."""
        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.url = "https://medium.com/@author/test"
        mock_article.description = None

        mock_digest = MagicMock()
        mock_digest.id = uuid.uuid4()
        mock_digest.subject = "Test"
        mock_digest.articles = [mock_article]
        mock_get_unsent.return_value = [mock_digest]

        provider = MediumAlertProvider(session=self.mock_session)
        alerts = provider.get_pending_alerts()

        self.assertEqual(alerts[0].items[0].metadata["description"], "")

    @patch("src.alerts.base.provider.mark_alerted")
    def test_mark_sent_calls_database(self, mock_mark: MagicMock) -> None:
        """Test that mark_sent calls mark_alerted."""
        test_id = uuid.uuid4()
        provider = MediumAlertProvider(session=self.mock_session)

        provider.mark_sent(str(test_id))

        mock_mark.assert_called_once()

    @patch("src.alerts.base.provider.get_unsent_by_alerted_at")
    def test_get_pending_alerts_empty_list(self, mock_get_unsent: MagicMock) -> None:
        """Test that empty result returns empty list."""
        mock_get_unsent.return_value = []

        provider = MediumAlertProvider(session=self.mock_session)
        alerts = provider.get_pending_alerts()

        self.assertEqual(alerts, [])


if __name__ == "__main__":
    unittest.main()
