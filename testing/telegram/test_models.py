"""Tests for Telegram models."""

import unittest

from src.telegram.models import (
    TelegramChat,
    TelegramEntity,
    TelegramMessageInfo,
)


class TestTelegramMessageInfoGetTextWithUrls(unittest.TestCase):
    """Tests for TelegramMessageInfo.get_text_with_urls method."""

    def _create_message(
        self,
        text: str | None,
        entities: list[TelegramEntity] | None = None,
    ) -> TelegramMessageInfo:
        """Create a test message with the given text and entities."""
        return TelegramMessageInfo(
            message_id=1,
            date=1234567890,
            chat=TelegramChat(id=12345, type="private"),
            text=text,
            entities=entities,
        )

    def test_returns_none_when_no_text(self) -> None:
        """Test that None is returned when message has no text."""
        message = self._create_message(text=None)

        result = message.get_text_with_urls()

        self.assertIsNone(result)

    def test_returns_text_when_no_entities(self) -> None:
        """Test that text is returned unchanged when no entities."""
        message = self._create_message(text="Hello world")

        result = message.get_text_with_urls()

        self.assertEqual(result, "Hello world")

    def test_returns_text_when_empty_entities(self) -> None:
        """Test that text is returned unchanged when entities list is empty."""
        message = self._create_message(text="Hello world", entities=[])

        result = message.get_text_with_urls()

        self.assertEqual(result, "Hello world")

    def test_replaces_text_link_with_url(self) -> None:
        """Test that text_link entity is replaced with its URL."""
        text = "Check out this article"
        entities = [
            TelegramEntity(
                type="text_link",
                offset=15,  # "article" starts at index 15
                length=7,
                url="https://example.com/full-article-path",
            )
        ]
        message = self._create_message(text=text, entities=entities)

        result = message.get_text_with_urls()

        self.assertEqual(result, "Check out this https://example.com/full-article-path")

    def test_replaces_multiple_text_links(self) -> None:
        """Test that multiple text_link entities are replaced."""
        text = "Read link1 and link2"
        entities = [
            TelegramEntity(
                type="text_link",
                offset=5,  # "link1"
                length=5,
                url="https://example.com/first",
            ),
            TelegramEntity(
                type="text_link",
                offset=15,  # "link2"
                length=5,
                url="https://example.com/second",
            ),
        ]
        message = self._create_message(text=text, entities=entities)

        result = message.get_text_with_urls()

        self.assertEqual(result, "Read https://example.com/first and https://example.com/second")

    def test_ignores_non_text_link_entities(self) -> None:
        """Test that non-text_link entities are ignored."""
        text = "Hello @username"
        entities = [
            TelegramEntity(
                type="mention",
                offset=6,
                length=9,
                url=None,
            )
        ]
        message = self._create_message(text=text, entities=entities)

        result = message.get_text_with_urls()

        self.assertEqual(result, "Hello @username")

    def test_ignores_text_link_without_url(self) -> None:
        """Test that text_link entities without URL are ignored."""
        text = "Check this link"
        entities = [
            TelegramEntity(
                type="text_link",
                offset=11,
                length=4,
                url=None,  # No URL
            )
        ]
        message = self._create_message(text=text, entities=entities)

        result = message.get_text_with_urls()

        self.assertEqual(result, "Check this link")

    def test_newsletter_format_example(self) -> None:
        """Test with realistic newsletter format from TLDR."""
        text = (
            "Da2a: The Future of Data Platforms (6 minute read)\n"
            "Traditional centralized data platforms create bottlenecks.\n"
            "mlops.community"
        )
        entities = [
            TelegramEntity(
                type="text_link",
                offset=113,  # "mlops.community"
                length=15,
                url="https://mlops.community/da2a-the-future-of-data-platforms/",
            )
        ]
        message = self._create_message(text=text, entities=entities)

        result = message.get_text_with_urls()

        self.assertIn("https://mlops.community/da2a-the-future-of-data-platforms/", result)
        self.assertNotIn("mlops.community\n", result)


if __name__ == "__main__":
    unittest.main()
