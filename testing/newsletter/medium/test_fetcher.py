"""Tests for Medium digest fetcher."""

import unittest
from datetime import UTC, datetime

from src.newsletters.base.fetcher import extract_email_metadata, parse_datetime
from src.newsletters.medium.fetcher import MEDIUM_SENDER_EMAIL


class TestMediumSenderEmail(unittest.TestCase):
    """Tests for Medium sender email constant."""

    def test_medium_sender_email_is_defined(self) -> None:
        """Should have a valid Medium sender email."""
        self.assertEqual(MEDIUM_SENDER_EMAIL, "noreply@medium.com")


class TestExtractEmailMetadata(unittest.TestCase):
    """Tests for extract_email_metadata function."""

    def test_extract_email_metadata_returns_expected_fields(self) -> None:
        """Should extract all expected fields from message."""
        message = {
            "id": "abc123",
            "subject": "Medium Daily Digest",
            "from": {
                "emailAddress": {
                    "name": "Medium",
                    "address": "noreply@medium.com",
                }
            },
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "body": {"content": "<html>Test content</html>"},
        }

        metadata = extract_email_metadata(message)

        self.assertEqual(metadata["email_id"], "abc123")
        self.assertEqual(metadata["subject"], "Medium Daily Digest")
        self.assertEqual(metadata["sender_name"], "Medium")
        self.assertEqual(metadata["sender_email"], "noreply@medium.com")
        self.assertEqual(metadata["body_html"], "<html>Test content</html>")
        self.assertIsInstance(metadata["received_at"], datetime)

    def test_extract_email_metadata_handles_missing_fields(self) -> None:
        """Should handle missing optional fields gracefully."""
        message: dict[str, object] = {
            "id": "abc123",
            "subject": "",
            "receivedDateTime": "2024-01-15T10:30:00Z",
        }

        metadata = extract_email_metadata(message)

        self.assertEqual(metadata["email_id"], "abc123")
        self.assertEqual(metadata["subject"], "")
        self.assertEqual(metadata["sender_name"], "")
        self.assertEqual(metadata["body_html"], "")


class TestParseDatetime(unittest.TestCase):
    """Tests for parse_datetime function."""

    def test_parse_datetime_z_suffix(self) -> None:
        """Should parse datetime with Z suffix."""
        result = parse_datetime("2024-01-15T10:30:00Z")
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        self.assertEqual(result, expected)

    def test_parse_datetime_offset_format(self) -> None:
        """Should parse datetime with timezone offset."""
        result = parse_datetime("2024-01-15T10:30:00+00:00")
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
