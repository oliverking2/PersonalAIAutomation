"""Tests for Substack alert provider."""

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.alerts.enums import AlertType
from src.alerts.providers.substack import SubstackAlertProvider


class TestSubstackAlertProvider(unittest.TestCase):
    """Tests for SubstackAlertProvider class."""

    def test_alert_type_is_substack(self) -> None:
        """Should return SUBSTACK alert type."""
        session = MagicMock()
        provider = SubstackAlertProvider(session)

        self.assertEqual(provider.alert_type, AlertType.SUBSTACK)

    @patch("src.alerts.providers.substack.get_unsent_substack_posts")
    def test_get_pending_alerts_returns_empty_when_no_posts(
        self, mock_get_unsent: MagicMock
    ) -> None:
        """Should return empty list when no unsent posts."""
        mock_get_unsent.return_value = []
        session = MagicMock()
        provider = SubstackAlertProvider(session)

        result = provider.get_pending_alerts()

        self.assertEqual(result, [])

    @patch("src.alerts.providers.substack.get_unsent_substack_posts")
    def test_get_pending_alerts_returns_one_alert_per_publication(
        self, mock_get_unsent: MagicMock
    ) -> None:
        """Should return one alert per publication."""
        # Create mock posts from two different publications
        newsletter1 = MagicMock()
        newsletter1.name = "Newsletter A"

        newsletter2 = MagicMock()
        newsletter2.name = "Newsletter B"

        post1 = MagicMock()
        post1.id = uuid.uuid4()
        post1.title = "Post 1"
        post1.url = "https://a.substack.com/p/post-1"
        post1.subtitle = "Subtitle 1"
        post1.is_paywalled = False
        post1.published_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        post1.newsletter = newsletter1

        post2 = MagicMock()
        post2.id = uuid.uuid4()
        post2.title = "Post 2"
        post2.url = "https://b.substack.com/p/post-2"
        post2.subtitle = None
        post2.is_paywalled = True
        post2.published_at = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
        post2.newsletter = newsletter2

        mock_get_unsent.return_value = [post1, post2]

        session = MagicMock()
        provider = SubstackAlertProvider(session)

        result = provider.get_pending_alerts()

        # Should return 2 alerts, one per publication
        self.assertEqual(len(result), 2)

        # Check each alert has correct structure
        alert_titles = {alert.title for alert in result}
        self.assertEqual(alert_titles, {"Newsletter A", "Newsletter B"})

        for alert in result:
            self.assertEqual(alert.alert_type, AlertType.SUBSTACK)
            self.assertEqual(len(alert.items), 1)  # One post per publication
            self.assertIn("is_paywalled", alert.items[0].metadata)

    @patch("src.alerts.providers.substack.get_unsent_substack_posts")
    def test_get_pending_alerts_groups_posts_within_same_publication(
        self, mock_get_unsent: MagicMock
    ) -> None:
        """Should group multiple posts from the same publication into one alert."""
        newsletter = MagicMock()
        newsletter.name = "Test Newsletter"

        post1 = MagicMock()
        post1.id = uuid.uuid4()
        post1.title = "Post 1"
        post1.url = "https://test.substack.com/p/post-1"
        post1.subtitle = None
        post1.is_paywalled = False
        post1.published_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        post1.newsletter = newsletter

        post2 = MagicMock()
        post2.id = uuid.uuid4()
        post2.title = "Post 2"
        post2.url = "https://test.substack.com/p/post-2"
        post2.subtitle = None
        post2.is_paywalled = False
        post2.published_at = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
        post2.newsletter = newsletter

        mock_get_unsent.return_value = [post1, post2]

        session = MagicMock()
        provider = SubstackAlertProvider(session)

        result = provider.get_pending_alerts()

        # Should return 1 alert with 2 items
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Test Newsletter")
        self.assertEqual(len(result[0].items), 2)

    @patch("src.alerts.providers.substack.get_unsent_substack_posts")
    @patch("src.alerts.providers.substack.mark_substack_post_alerted")
    def test_mark_sent_marks_posts_for_specific_source(
        self,
        mock_mark_alerted: MagicMock,
        mock_get_unsent: MagicMock,
    ) -> None:
        """Should mark only posts belonging to the specified source_id."""
        post1_id = uuid.uuid4()
        post2_id = uuid.uuid4()

        newsletter = MagicMock()
        newsletter.name = "Test Newsletter"

        post1 = MagicMock()
        post1.id = post1_id
        post1.title = "Post 1"
        post1.url = "https://test.substack.com/p/post-1"
        post1.subtitle = None
        post1.is_paywalled = False
        post1.published_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        post1.newsletter = newsletter

        post2 = MagicMock()
        post2.id = post2_id
        post2.title = "Post 2"
        post2.url = "https://test.substack.com/p/post-2"
        post2.subtitle = None
        post2.is_paywalled = False
        post2.published_at = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
        post2.newsletter = newsletter

        mock_get_unsent.return_value = [post1, post2]

        session = MagicMock()
        provider = SubstackAlertProvider(session)

        # First get pending alerts to populate tracking
        alerts = provider.get_pending_alerts()
        self.assertEqual(len(alerts), 1)

        # Mark as sent using the correct source_id from the alert
        provider.mark_sent(alerts[0].source_id)

        # Should have called mark_alerted for each post
        self.assertEqual(mock_mark_alerted.call_count, 2)
        call_args = [call[0][1] for call in mock_mark_alerted.call_args_list]
        self.assertIn(post1_id, call_args)
        self.assertIn(post2_id, call_args)

    @patch("src.alerts.providers.substack.get_unsent_substack_posts")
    @patch("src.alerts.providers.substack.mark_substack_post_alerted")
    def test_mark_sent_with_unknown_source_id_does_nothing(
        self,
        mock_mark_alerted: MagicMock,
        mock_get_unsent: MagicMock,
    ) -> None:
        """Should not mark any posts if source_id is not found."""
        mock_get_unsent.return_value = []

        session = MagicMock()
        provider = SubstackAlertProvider(session)

        provider.mark_sent("unknown-source-id")

        mock_mark_alerted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
