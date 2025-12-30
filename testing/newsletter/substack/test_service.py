"""Tests for Substack newsletter service."""

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.newsletters.substack.models import SubstackProcessingResult
from src.newsletters.substack.service import SubstackService


class TestSubstackService(unittest.TestCase):
    """Tests for SubstackService class."""

    @patch("src.newsletters.substack.service.User")
    def test_process_publications_returns_empty_result_when_no_publications(
        self,
        mock_user_class: MagicMock,
    ) -> None:
        """Should return empty result when no publications are configured."""
        mock_user = MagicMock()
        mock_user.get_subscriptions.return_value = []
        mock_user_class.return_value = mock_user

        session = MagicMock()
        service = SubstackService(session)

        result = service.process_publications()

        self.assertEqual(result.posts_processed, 0)
        self.assertEqual(result.posts_new, 0)
        self.assertEqual(result.posts_duplicate, 0)
        self.assertEqual(len(result.errors), 0)

    @patch("src.newsletters.substack.service.ensure_newsletters_exist")
    @patch("src.newsletters.substack.service.Newsletter")
    @patch("src.newsletters.substack.service.User")
    def test_process_publications_skips_old_posts(
        self,
        mock_user_class: MagicMock,
        mock_newsletter_class: MagicMock,
        mock_ensure: MagicMock,
    ) -> None:
        """Should skip posts older than watermark."""
        # Set up User mock to return subscriptions
        # Note: domain should NOT include https:// prefix - service adds it
        mock_user = MagicMock()
        mock_user.get_subscriptions.return_value = [
            {"domain": "test.substack.com", "publication_name": "Test"}
        ]
        mock_user_class.return_value = mock_user

        session = MagicMock()
        newsletter_id = uuid.uuid4()
        mock_ensure.return_value = {"https://test.substack.com": newsletter_id}

        # Create mock post with old date
        mock_post = MagicMock()
        mock_post.url = "https://test.substack.com/p/old-post"
        mock_post.get_metadata.return_value = {
            "id": "123",
            "title": "Old Post",
            "post_date": "2024-01-01T00:00:00Z",
            "canonical_url": "https://test.substack.com/p/old-post",
        }

        mock_newsletter = MagicMock()
        mock_newsletter.get_posts.return_value = [mock_post]
        mock_newsletter_class.return_value = mock_newsletter

        service = SubstackService(session)
        # Set watermark to after the post date
        since = datetime(2024, 1, 10, 0, 0, 0, tzinfo=UTC)
        result = service.process_publications(since=since)

        # Post should be skipped (not processed or marked as duplicate)
        self.assertEqual(result.posts_new, 0)
        self.assertEqual(result.posts_processed, 0)

    @patch("src.newsletters.substack.service.ensure_newsletters_exist")
    @patch("src.newsletters.substack.service.Newsletter")
    @patch("src.newsletters.substack.service.User")
    @patch("src.newsletters.substack.service.substack_post_exists")
    def test_process_publications_skips_duplicate_posts(
        self,
        mock_exists: MagicMock,
        mock_user_class: MagicMock,
        mock_newsletter_class: MagicMock,
        mock_ensure: MagicMock,
    ) -> None:
        """Should skip posts that already exist."""
        # Set up User mock to return subscriptions
        # Note: domain should NOT include https:// prefix - service adds it
        mock_user = MagicMock()
        mock_user.get_subscriptions.return_value = [
            {"domain": "test.substack.com", "publication_name": "Test"}
        ]
        mock_user_class.return_value = mock_user

        session = MagicMock()
        newsletter_id = uuid.uuid4()
        mock_ensure.return_value = {"https://test.substack.com": newsletter_id}
        mock_exists.return_value = True  # Post exists

        mock_post = MagicMock()
        mock_post.url = "https://test.substack.com/p/existing-post"
        mock_post.get_metadata.return_value = {
            "id": "123",
            "title": "Existing Post",
            "post_date": "2024-01-15T00:00:00Z",
            "canonical_url": "https://test.substack.com/p/existing-post",
        }

        mock_newsletter = MagicMock()
        mock_newsletter.get_posts.return_value = [mock_post]
        mock_newsletter_class.return_value = mock_newsletter

        service = SubstackService(session)
        result = service.process_publications()

        self.assertEqual(result.posts_duplicate, 1)
        self.assertEqual(result.posts_new, 0)


class TestSubstackProcessingResult(unittest.TestCase):
    """Tests for SubstackProcessingResult model."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        result = SubstackProcessingResult()

        self.assertEqual(result.posts_processed, 0)
        self.assertEqual(result.posts_new, 0)
        self.assertEqual(result.posts_duplicate, 0)
        self.assertEqual(result.errors, [])
        self.assertIsNone(result.latest_published_at)

    def test_tracks_latest_published_at(self) -> None:
        """Should track latest_published_at field."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = SubstackProcessingResult(latest_published_at=timestamp)

        self.assertEqual(result.latest_published_at, timestamp)


if __name__ == "__main__":
    unittest.main()
