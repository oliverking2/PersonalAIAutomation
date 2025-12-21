"""Tests for Telegram service module."""

import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock

from src.telegram.client import TelegramClientError
from src.telegram.models import SendResult
from src.telegram.service import TelegramService


class TestTelegramServiceSendUnsentNewsletters(unittest.TestCase):
    """Tests for TelegramService.send_unsent_newsletters method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.mock_client = MagicMock()

    def _create_mock_newsletter(
        self,
        *,
        subject: str = "Test Newsletter",
        alerted_at: datetime | None = None,
    ) -> MagicMock:
        """Create a mock Newsletter object.

        :param subject: The newsletter subject.
        :param alerted_at: When the newsletter was alerted (None if not alerted).
        :returns: A mock Newsletter object.
        """
        newsletter = MagicMock()
        newsletter.id = uuid.uuid4()
        newsletter.subject = subject
        newsletter.alerted_at = alerted_at
        newsletter.articles = []
        return newsletter

    def _create_mock_article(
        self,
        *,
        title: str = "Test Article",
        url: str = "https://example.com/article",
    ) -> MagicMock:
        """Create a mock Article object.

        :param title: The article title.
        :param url: The article URL.
        :returns: A mock Article object.
        """
        article = MagicMock()
        article.title = title
        article.url = url
        return article

    def test_send_unsent_newsletters_no_newsletters_returns_zero(self) -> None:
        """Test that no newsletters results in zero sent count."""
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        service = TelegramService(self.mock_session, self.mock_client)
        result = service.send_unsent_newsletters()

        self.assertIsInstance(result, SendResult)
        self.assertEqual(result.newsletters_sent, 0)
        self.assertEqual(result.errors, [])

    def test_send_unsent_newsletters_sends_all_unsent(self) -> None:
        """Test that all unsent newsletters are sent."""
        newsletters = [
            self._create_mock_newsletter(subject="Newsletter 1"),
            self._create_mock_newsletter(subject="Newsletter 2"),
        ]
        for nl in newsletters:
            nl.articles = [self._create_mock_article()]

        self.mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = newsletters
        self.mock_client.send_message.return_value = True

        service = TelegramService(self.mock_session, self.mock_client)
        result = service.send_unsent_newsletters()

        self.assertEqual(result.newsletters_sent, 2)
        self.assertEqual(self.mock_client.send_message.call_count, 2)

    def test_send_unsent_newsletters_updates_alerted_at(self) -> None:
        """Test that alerted_at is updated after successful send."""
        newsletter = self._create_mock_newsletter()
        newsletter.articles = [self._create_mock_article()]
        self.assertIsNone(newsletter.alerted_at)

        # Mock for get_unsent_newsletters (ends with .all())
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            newsletter
        ]
        # Mock for mark_newsletter_alerted (ends with .one())
        self.mock_session.query.return_value.filter.return_value.one.return_value = newsletter
        self.mock_client.send_message.return_value = True

        service = TelegramService(self.mock_session, self.mock_client)
        service.send_unsent_newsletters()

        self.assertIsNotNone(newsletter.alerted_at)
        self.assertIsInstance(newsletter.alerted_at, datetime)
        self.mock_session.flush.assert_called()

    def test_send_unsent_newsletters_client_error_adds_to_errors(self) -> None:
        """Test that client errors are captured in result."""
        newsletter = self._create_mock_newsletter()
        newsletter.articles = [self._create_mock_article()]

        self.mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            newsletter
        ]
        self.mock_client.send_message.side_effect = TelegramClientError("API error")

        service = TelegramService(self.mock_session, self.mock_client)
        result = service.send_unsent_newsletters()

        self.assertEqual(result.newsletters_sent, 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("API error", result.errors[0])

    def test_send_unsent_newsletters_partial_failure(self) -> None:
        """Test that some newsletters can succeed while others fail."""
        newsletter_success = self._create_mock_newsletter(subject="Success")
        newsletter_success.articles = [self._create_mock_article()]
        newsletter_fail = self._create_mock_newsletter(subject="Fail")
        newsletter_fail.articles = [self._create_mock_article()]

        self.mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            newsletter_success,
            newsletter_fail,
        ]
        self.mock_client.send_message.side_effect = [
            True,
            TelegramClientError("Failed"),
        ]

        service = TelegramService(self.mock_session, self.mock_client)
        result = service.send_unsent_newsletters()

        self.assertEqual(result.newsletters_sent, 1)
        self.assertEqual(len(result.errors), 1)


class TestTelegramServiceFormatMessage(unittest.TestCase):
    """Tests for TelegramService._format_newsletter_message method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.mock_client = MagicMock()
        self.service = TelegramService(self.mock_session, self.mock_client)

    def _create_mock_newsletter(self, *, subject: str = "Test Subject") -> MagicMock:
        """Create a mock Newsletter object.

        :param subject: The newsletter subject.
        :returns: A mock Newsletter object.
        """
        newsletter = MagicMock()
        newsletter.subject = subject
        newsletter.articles = []
        return newsletter

    def _create_mock_article(
        self,
        *,
        title: str = "Article Title",
        url: str = "https://example.com",
    ) -> MagicMock:
        """Create a mock Article object.

        :param title: The article title.
        :param url: The article URL.
        :returns: A mock Article object.
        """
        article = MagicMock()
        article.title = title
        article.url = url
        return article

    def test_format_message_includes_subject_as_bold(self) -> None:
        """Test that newsletter subject is formatted as bold HTML."""
        newsletter = self._create_mock_newsletter(subject="My Newsletter")
        newsletter.articles = []

        message = self.service._format_newsletter_message(newsletter)

        self.assertIn("<b>My Newsletter</b>", message)

    def test_format_message_includes_article_titles_and_urls(self) -> None:
        """Test that article titles and URLs are included."""
        newsletter = self._create_mock_newsletter()
        newsletter.articles = [
            self._create_mock_article(title="Article 1", url="https://example.com/1"),
            self._create_mock_article(title="Article 2", url="https://example.com/2"),
        ]

        message = self.service._format_newsletter_message(newsletter)

        self.assertIn("- Article 1", message)
        self.assertIn("https://example.com/1", message)
        self.assertIn("- Article 2", message)
        self.assertIn("https://example.com/2", message)

    def test_format_message_handles_empty_articles(self) -> None:
        """Test that newsletter with no articles formats correctly."""
        newsletter = self._create_mock_newsletter(subject="Empty Newsletter")
        newsletter.articles = []

        message = self.service._format_newsletter_message(newsletter)

        self.assertEqual(message, "<b>Empty Newsletter</b>")

    def test_format_message_preserves_article_order(self) -> None:
        """Test that articles appear in the same order as provided."""
        newsletter = self._create_mock_newsletter()
        newsletter.articles = [
            self._create_mock_article(title="First"),
            self._create_mock_article(title="Second"),
            self._create_mock_article(title="Third"),
        ]

        message = self.service._format_newsletter_message(newsletter)

        first_pos = message.find("First")
        second_pos = message.find("Second")
        third_pos = message.find("Third")

        self.assertLess(first_pos, second_pos)
        self.assertLess(second_pos, third_pos)


if __name__ == "__main__":
    unittest.main()
