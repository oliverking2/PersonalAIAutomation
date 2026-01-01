"""Tests for Medium digest service."""

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.newsletters.base.models import ProcessingResult
from src.newsletters.medium.models import ParsedMediumArticle
from src.newsletters.medium.service import MediumService


class TestProcessingResult(unittest.TestCase):
    """Tests for ProcessingResult model."""

    def test_default_values(self) -> None:
        """Should initialise with zero values."""
        result = ProcessingResult()

        self.assertEqual(result.digests_processed, 0)
        self.assertEqual(result.articles_extracted, 0)
        self.assertEqual(result.articles_new, 0)
        self.assertEqual(result.articles_duplicate, 0)
        self.assertEqual(result.errors, [])
        self.assertIsNone(result.latest_received_at)


class TestMediumService(unittest.TestCase):
    """Tests for MediumService."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.mock_graph_client = MagicMock()

    @patch("src.newsletters.base.service.fetch_emails")
    def test_process_digests_returns_result(self, mock_fetch: MagicMock) -> None:
        """Should return a ProcessingResult."""
        mock_fetch.return_value = []

        service = MediumService(
            session=self.mock_session,
            graph_client=self.mock_graph_client,
        )
        result = service.process_digests(since=None)

        self.assertIsInstance(result, ProcessingResult)

    @patch("src.newsletters.base.service.fetch_emails")
    def test_process_digests_passes_parameters(self, mock_fetch: MagicMock) -> None:
        """Should pass since and limit to fetch_emails."""
        mock_fetch.return_value = []
        since = datetime(2024, 1, 1, tzinfo=UTC)

        service = MediumService(
            session=self.mock_session,
            graph_client=self.mock_graph_client,
        )
        service.process_digests(since=since, limit=50)

        mock_fetch.assert_called_once_with(
            self.mock_graph_client,
            "noreply@medium.com",
            since=since,
            limit=50,
        )

    @patch("src.newsletters.medium.service.create_digest")
    @patch("src.newsletters.medium.service.parse_medium_digest")
    @patch("src.newsletters.base.service.record_exists_by_field")
    @patch("src.newsletters.base.service.extract_email_metadata")
    @patch("src.newsletters.base.service.fetch_emails")
    def test_process_digests_processes_new_digest(
        self,
        mock_fetch: MagicMock,
        mock_extract: MagicMock,
        mock_exists: MagicMock,
        mock_parse: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """Should process a new digest and update stats."""
        mock_fetch.return_value = [{"id": "msg1"}]
        mock_extract.return_value = {
            "email_id": "msg1",
            "subject": "Medium Daily Digest",
            "received_at": datetime(2024, 1, 15, tzinfo=UTC),
            "body_html": "<html>test</html>",
        }
        mock_exists.return_value = False
        mock_parse.return_value = [
            ParsedMediumArticle(
                title="Article 1",
                url="https://medium.com/@author/article-1",
            ),
            ParsedMediumArticle(
                title="Article 2",
                url="https://medium.com/@author/article-2",
            ),
        ]
        mock_create.return_value = (MagicMock(), 2, 0)  # 2 new, 0 dup

        service = MediumService(
            session=self.mock_session,
            graph_client=self.mock_graph_client,
        )
        result = service.process_digests(since=None)

        self.assertEqual(result.digests_processed, 1)
        self.assertEqual(result.articles_extracted, 2)
        self.assertEqual(result.articles_new, 2)
        self.assertEqual(result.articles_duplicate, 0)

    @patch("src.newsletters.base.service.record_exists_by_field")
    @patch("src.newsletters.base.service.extract_email_metadata")
    @patch("src.newsletters.base.service.fetch_emails")
    def test_process_digests_skips_existing_digest(
        self,
        mock_fetch: MagicMock,
        mock_extract: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Should skip already-processed digests."""
        mock_fetch.return_value = [{"id": "msg1"}]
        mock_extract.return_value = {
            "email_id": "msg1",
            "subject": "Medium Daily Digest",
            "received_at": datetime(2024, 1, 15, tzinfo=UTC),
            "body_html": "<html>test</html>",
        }
        mock_exists.return_value = True  # record_exists_by_field returns True

        service = MediumService(
            session=self.mock_session,
            graph_client=self.mock_graph_client,
        )
        result = service.process_digests(since=None)

        self.assertEqual(result.digests_processed, 0)

    @patch("src.newsletters.base.service.record_exists_by_field")
    @patch("src.newsletters.base.service.extract_email_metadata")
    @patch("src.newsletters.base.service.fetch_emails")
    def test_process_digests_catches_errors(
        self,
        mock_fetch: MagicMock,
        mock_extract: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Should catch and record errors."""
        mock_fetch.return_value = [{"id": "msg1"}]
        mock_extract.return_value = {
            "email_id": "msg1",
            "subject": "Test",
            "received_at": datetime(2024, 1, 15, tzinfo=UTC),
            "body_html": "<html>test</html>",
        }
        mock_exists.side_effect = Exception("Database error")

        service = MediumService(
            session=self.mock_session,
            graph_client=self.mock_graph_client,
        )
        result = service.process_digests(since=None)

        self.assertEqual(len(result.errors), 1)
        self.assertIn("Database error", result.errors[0])

    @patch("src.newsletters.medium.service.create_digest")
    @patch("src.newsletters.medium.service.parse_medium_digest")
    @patch("src.newsletters.base.service.record_exists_by_field")
    @patch("src.newsletters.base.service.extract_email_metadata")
    @patch("src.newsletters.base.service.fetch_emails")
    def test_process_digests_updates_latest_received_at(
        self,
        mock_fetch: MagicMock,
        mock_extract: MagicMock,
        mock_exists: MagicMock,
        mock_parse: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """Should track latest received_at."""
        mock_fetch.return_value = [{"id": "msg1"}, {"id": "msg2"}]
        earliest = datetime(2024, 1, 14, tzinfo=UTC)
        latest = datetime(2024, 1, 15, tzinfo=UTC)
        mock_extract.side_effect = [
            {
                "email_id": "msg1",
                "subject": "Digest 1",
                "received_at": earliest,
                "body_html": "<html>1</html>",
            },
            {
                "email_id": "msg2",
                "subject": "Digest 2",
                "received_at": latest,
                "body_html": "<html>2</html>",
            },
        ]
        mock_exists.return_value = False
        mock_parse.return_value = []
        mock_create.return_value = (MagicMock(), 0, 0)

        service = MediumService(
            session=self.mock_session,
            graph_client=self.mock_graph_client,
        )
        result = service.process_digests(since=None)

        self.assertEqual(result.latest_received_at, latest)


if __name__ == "__main__":
    unittest.main()
