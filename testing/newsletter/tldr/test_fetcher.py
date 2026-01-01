"""Tests for newsletter fetcher module."""

import unittest
from datetime import datetime

from src.newsletters.base.fetcher import extract_email_metadata, parse_datetime


class TestParseDateTime(unittest.TestCase):
    """Tests for parse_datetime function."""

    def test_parses_z_suffix_datetime(self) -> None:
        """Test parsing datetime with Z suffix."""
        result = parse_datetime("2024-01-15T10:30:00Z")

        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)
        self.assertEqual(result.hour, 10)
        self.assertEqual(result.minute, 30)
        self.assertIsNotNone(result.tzinfo)

    def test_parses_offset_datetime(self) -> None:
        """Test parsing datetime with timezone offset."""
        result = parse_datetime("2024-01-15T10:30:00+00:00")

        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parses_positive_offset(self) -> None:
        """Test parsing datetime with positive offset."""
        result = parse_datetime("2024-01-15T10:30:00+05:30")

        self.assertEqual(result.hour, 10)
        self.assertIsNotNone(result.tzinfo)


class TestExtractEmailMetadata(unittest.TestCase):
    """Tests for extract_email_metadata function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.sample_message = {
            "id": "test-message-id-123",
            "subject": "TLDR AI 2024-01-15",
            "from": {
                "emailAddress": {
                    "name": "TLDR AI",
                    "address": "dan@tldrnewsletter.com",
                }
            },
            "receivedDateTime": "2024-01-15T08:00:00Z",
            "body": {
                "content": "<html><body>Newsletter content</body></html>",
            },
        }

    def test_extracts_email_id(self) -> None:
        """Test extraction of email ID."""
        result = extract_email_metadata(self.sample_message)
        self.assertEqual(result["email_id"], "test-message-id-123")

    def test_extracts_subject(self) -> None:
        """Test extraction of subject."""
        result = extract_email_metadata(self.sample_message)
        self.assertEqual(result["subject"], "TLDR AI 2024-01-15")

    def test_extracts_sender_name(self) -> None:
        """Test extraction of sender display name."""
        result = extract_email_metadata(self.sample_message)
        self.assertEqual(result["sender_name"], "TLDR AI")

    def test_extracts_sender_email(self) -> None:
        """Test extraction of sender email address."""
        result = extract_email_metadata(self.sample_message)
        self.assertEqual(result["sender_email"], "dan@tldrnewsletter.com")

    def test_extracts_received_at(self) -> None:
        """Test extraction of received datetime."""
        result = extract_email_metadata(self.sample_message)
        self.assertIsInstance(result["received_at"], datetime)
        self.assertEqual(result["received_at"].year, 2024)
        self.assertEqual(result["received_at"].month, 1)
        self.assertEqual(result["received_at"].day, 15)

    def test_extracts_body_html(self) -> None:
        """Test extraction of body HTML content."""
        result = extract_email_metadata(self.sample_message)
        self.assertEqual(
            result["body_html"],
            "<html><body>Newsletter content</body></html>",
        )

    def test_handles_missing_fields_gracefully(self) -> None:
        """Test that missing fields default to empty strings."""
        minimal_message: dict[str, object] = {"receivedDateTime": "2024-01-15T08:00:00Z"}
        result = extract_email_metadata(minimal_message)

        self.assertEqual(result["email_id"], "")
        self.assertEqual(result["subject"], "")
        self.assertEqual(result["sender_name"], "")
        self.assertEqual(result["sender_email"], "")
        self.assertEqual(result["body_html"], "")


if __name__ == "__main__":
    unittest.main()
