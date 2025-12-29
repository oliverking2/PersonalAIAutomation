"""Tests for Substack database operations."""

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.database.substack import (
    SubstackPostData,
    create_substack_post,
    get_or_create_newsletter,
    get_unsent_substack_posts,
    mark_substack_post_alerted,
    substack_post_exists,
)
from src.database.substack.models import SubstackNewsletter, SubstackPost


class TestGetOrCreateNewsletter(unittest.TestCase):
    """Tests for get_or_create_newsletter function."""

    def test_returns_existing_newsletter(self) -> None:
        """Should return existing newsletter when it exists."""
        existing = MagicMock()
        existing.name = "Test Newsletter"

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = existing

        result = get_or_create_newsletter(session, "https://test.substack.com", "Test Newsletter")

        self.assertEqual(result, existing)
        session.add.assert_not_called()

    def test_creates_new_newsletter_when_none_exists(self) -> None:
        """Should create new newsletter when none exists."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        result = get_or_create_newsletter(session, "https://test.substack.com", "Test Newsletter")

        session.add.assert_called_once()
        session.flush.assert_called_once()
        self.assertIsInstance(result, SubstackNewsletter)
        self.assertEqual(result.url, "https://test.substack.com")
        self.assertEqual(result.name, "Test Newsletter")

    def test_updates_name_if_changed(self) -> None:
        """Should update newsletter name if it changed."""
        existing = MagicMock()
        existing.name = "Old Name"

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = existing

        result = get_or_create_newsletter(session, "https://test.substack.com", "New Name")

        self.assertEqual(existing.name, "New Name")
        self.assertEqual(result, existing)


class TestSubstackPostExists(unittest.TestCase):
    """Tests for substack_post_exists function."""

    def test_returns_true_when_post_exists(self) -> None:
        """Should return True when post exists."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = MagicMock()

        result = substack_post_exists(session, "post-123")

        self.assertTrue(result)

    def test_returns_false_when_post_not_exists(self) -> None:
        """Should return False when post doesn't exist."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        result = substack_post_exists(session, "post-123")

        self.assertFalse(result)


class TestCreateSubstackPost(unittest.TestCase):
    """Tests for create_substack_post function."""

    def test_creates_post_with_all_fields(self) -> None:
        """Should create post with all fields populated."""
        session = MagicMock()
        newsletter_id = uuid.uuid4()

        post_data = SubstackPostData(
            newsletter_id=newsletter_id,
            post_id="post-123",
            title="Test Post",
            subtitle="A test subtitle",
            url="https://test.substack.com/p/test-post",
            is_paywalled=True,
            published_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        result = create_substack_post(session, post_data)

        session.add.assert_called_once()
        session.flush.assert_called_once()
        self.assertIsInstance(result, SubstackPost)
        self.assertEqual(result.newsletter_id, newsletter_id)
        self.assertEqual(result.post_id, "post-123")
        self.assertEqual(result.title, "Test Post")
        self.assertEqual(result.subtitle, "A test subtitle")
        self.assertTrue(result.is_paywalled)

    def test_creates_post_without_optional_fields(self) -> None:
        """Should create post without optional subtitle."""
        session = MagicMock()
        newsletter_id = uuid.uuid4()

        post_data = SubstackPostData(
            newsletter_id=newsletter_id,
            post_id="post-456",
            title="Test Post",
            subtitle=None,
            url="https://test.substack.com/p/test-post",
            is_paywalled=False,
            published_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        result = create_substack_post(session, post_data)

        self.assertIsInstance(result, SubstackPost)
        self.assertIsNone(result.subtitle)
        self.assertFalse(result.is_paywalled)


class TestGetUnsentSubstackPosts(unittest.TestCase):
    """Tests for get_unsent_substack_posts function."""

    def test_returns_posts_with_null_alerted_at(self) -> None:
        """Should return posts where alerted_at is NULL."""
        post1 = MagicMock()
        post2 = MagicMock()

        session = MagicMock()
        (
            session.query.return_value.options.return_value.filter.return_value.order_by.return_value.all
        ).return_value = [post1, post2]

        result = get_unsent_substack_posts(session)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], post1)
        self.assertEqual(result[1], post2)


class TestMarkSubstackPostAlerted(unittest.TestCase):
    """Tests for mark_substack_post_alerted function."""

    def test_sets_alerted_at_timestamp(self) -> None:
        """Should set alerted_at to current time."""
        post = MagicMock()
        post.alerted_at = None
        post_id = uuid.uuid4()

        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = post

        mark_substack_post_alerted(session, post_id)

        self.assertIsNotNone(post.alerted_at)
        self.assertIsInstance(post.alerted_at, datetime)
        session.flush.assert_called_once()


class TestSubstackModels(unittest.TestCase):
    """Tests for Substack ORM models."""

    def test_newsletter_repr(self) -> None:
        """Should return readable string representation for newsletter."""
        newsletter = SubstackNewsletter(
            url="https://test.substack.com",
            name="Test Newsletter",
        )

        result = repr(newsletter)

        self.assertIn("SubstackNewsletter", result)
        self.assertIn("Test Newsletter", result)

    def test_post_repr(self) -> None:
        """Should return readable string representation for post."""
        post = SubstackPost(
            newsletter_id=uuid.uuid4(),
            post_id="test-post",
            title="Test Post Title",
            url="https://test.substack.com/p/test-post",
            published_at=datetime.now(UTC),
        )

        result = repr(post)

        self.assertIn("SubstackPost", result)
        self.assertIn("Test Post Title", result)


if __name__ == "__main__":
    unittest.main()
