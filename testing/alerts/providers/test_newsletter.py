"""Tests for NewsletterAlertProvider."""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from src.alerts.enums import AlertType
from src.alerts.providers.newsletter import NewsletterAlertProvider


class TestNewsletterAlertProvider(unittest.TestCase):
    """Tests for NewsletterAlertProvider."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()

    def test_alert_type(self) -> None:
        """Test that alert_type returns NEWSLETTER."""
        provider = NewsletterAlertProvider(session=self.mock_session)
        self.assertEqual(provider.alert_type, AlertType.NEWSLETTER)

    @patch("src.alerts.providers.newsletter.get_unsent_newsletters")
    def test_get_pending_alerts_converts_newsletters(self, mock_get_unsent: MagicMock) -> None:
        """Test that newsletters are converted to AlertData."""
        mock_newsletter = MagicMock()
        mock_newsletter.id = uuid.uuid4()
        mock_newsletter.newsletter_type.value = "TLDR AI"
        mock_newsletter.subject = "Issue 123"
        mock_newsletter.articles = []
        mock_get_unsent.return_value = [mock_newsletter]

        provider = NewsletterAlertProvider(session=self.mock_session)
        alerts = provider.get_pending_alerts()

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, AlertType.NEWSLETTER)
        self.assertEqual(alerts[0].source_id, str(mock_newsletter.id))
        self.assertIn("TLDR AI", alerts[0].title)
        self.assertIn("Issue 123", alerts[0].title)

    @patch("src.alerts.providers.newsletter.get_unsent_newsletters")
    def test_get_pending_alerts_includes_articles(self, mock_get_unsent: MagicMock) -> None:
        """Test that articles are included as items."""
        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.url = "https://example.com"
        mock_article.url_parsed = None
        mock_article.description = "Article description"

        mock_newsletter = MagicMock()
        mock_newsletter.id = uuid.uuid4()
        mock_newsletter.newsletter_type.value = "Test"
        mock_newsletter.subject = "Test"
        mock_newsletter.articles = [mock_article]
        mock_get_unsent.return_value = [mock_newsletter]

        provider = NewsletterAlertProvider(session=self.mock_session)
        alerts = provider.get_pending_alerts()

        self.assertEqual(len(alerts[0].items), 1)
        self.assertEqual(alerts[0].items[0].name, "Test Article")
        self.assertEqual(alerts[0].items[0].url, "https://example.com")

    @patch("src.alerts.providers.newsletter.mark_newsletter_alerted")
    def test_mark_sent_calls_database(self, mock_mark: MagicMock) -> None:
        """Test that mark_sent calls mark_newsletter_alerted."""
        test_id = uuid.uuid4()
        provider = NewsletterAlertProvider(session=self.mock_session)

        provider.mark_sent(str(test_id))

        mock_mark.assert_called_once_with(self.mock_session, test_id)


if __name__ == "__main__":
    unittest.main()
