"""Tests for Medium database operations."""

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.database.base import compute_url_hash, record_exists_by_field
from src.database.medium import create_digest
from src.database.medium.models import MediumDigest
from src.newsletters.medium.models import ParsedMediumArticle, ParsedMediumDigest


class TestComputeUrlHash(unittest.TestCase):
    """Tests for compute_url_hash function."""

    def test_computes_sha256_hash(self) -> None:
        """Should compute SHA256 hash of URL."""
        url = "https://medium.com/@author/article"
        result = compute_url_hash(url)

        self.assertEqual(len(result), 64)  # SHA256 hex is 64 chars
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_normalises_url_before_hashing(self) -> None:
        """Should normalise URL (lowercase, strip, remove trailing slash)."""
        url1 = "https://medium.com/@author/article/"
        url2 = "HTTPS://MEDIUM.COM/@author/article"
        url3 = "  https://medium.com/@author/article  "

        self.assertEqual(compute_url_hash(url1), compute_url_hash(url2))
        self.assertEqual(compute_url_hash(url1), compute_url_hash(url3))


class TestRecordExistsByField(unittest.TestCase):
    """Tests for record_exists_by_field function."""

    def test_returns_true_when_record_exists(self) -> None:
        """Should return True when record exists."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = MagicMock()

        result = record_exists_by_field(session, MediumDigest, "email_id", "email-123")

        self.assertTrue(result)

    def test_returns_false_when_record_not_exists(self) -> None:
        """Should return False when record doesn't exist."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        result = record_exists_by_field(session, MediumDigest, "email_id", "email-123")

        self.assertFalse(result)


class TestCreateDigest(unittest.TestCase):
    """Tests for create_digest function."""

    def test_creates_digest_with_articles(self) -> None:
        """Should create digest and articles."""
        session = MagicMock()
        # No duplicate articles
        session.query.return_value.filter.return_value.first.return_value = None

        parsed = ParsedMediumDigest(
            email_id="email-123",
            subject="Medium Daily Digest",
            received_at=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            articles=[
                ParsedMediumArticle(
                    title="Article 1 (5 min read)",
                    url="https://medium.com/@author/article-1",
                    description="Description 1",
                    read_time_minutes=5,
                ),
                ParsedMediumArticle(
                    title="Article 2 (3 min read)",
                    url="https://medium.com/@author/article-2",
                    description="Description 2",
                    read_time_minutes=3,
                ),
            ],
        )

        digest, new_count, dup_count = create_digest(session, parsed)

        self.assertIsInstance(digest, MediumDigest)
        self.assertEqual(digest.email_id, "email-123")
        self.assertEqual(new_count, 2)
        self.assertEqual(dup_count, 0)
        # 1 digest + 2 articles = 3 adds
        self.assertEqual(session.add.call_count, 3)

    def test_skips_duplicate_articles(self) -> None:
        """Should skip articles that already exist."""
        session = MagicMock()
        # All articles are duplicates
        session.query.return_value.filter.return_value.first.return_value = MagicMock()

        parsed = ParsedMediumDigest(
            email_id="email-123",
            subject="Medium Daily Digest",
            received_at=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            articles=[
                ParsedMediumArticle(
                    title="Duplicate Article",
                    url="https://medium.com/@author/duplicate",
                    description="Description",
                    read_time_minutes=5,
                ),
            ],
        )

        _digest, new_count, dup_count = create_digest(session, parsed)

        self.assertEqual(new_count, 0)
        self.assertEqual(dup_count, 1)
        # Only 1 add for digest, articles skipped
        self.assertEqual(session.add.call_count, 1)


if __name__ == "__main__":
    unittest.main()
