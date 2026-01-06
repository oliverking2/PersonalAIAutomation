"""Tests for Telegram models."""

import unittest

from src.telegram.models import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    TelegramChat,
    TelegramEntity,
    TelegramMessageInfo,
    TelegramUpdate,
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


class TestInlineKeyboardButton(unittest.TestCase):
    """Tests for InlineKeyboardButton model."""

    def test_button_with_callback_data(self) -> None:
        """Test creating a button with callback data."""
        button = InlineKeyboardButton(
            text="Click me",
            callback_data="action:123",
        )

        self.assertEqual(button.text, "Click me")
        self.assertEqual(button.callback_data, "action:123")
        self.assertIsNone(button.url)

    def test_button_with_url(self) -> None:
        """Test creating a button with URL."""
        button = InlineKeyboardButton(
            text="Visit site",
            url="https://example.com",
        )

        self.assertEqual(button.text, "Visit site")
        self.assertIsNone(button.callback_data)
        self.assertEqual(button.url, "https://example.com")


class TestInlineKeyboardMarkup(unittest.TestCase):
    """Tests for InlineKeyboardMarkup model."""

    def test_single_row_keyboard(self) -> None:
        """Test creating a keyboard with a single row."""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Button 1", callback_data="b1"),
                    InlineKeyboardButton(text="Button 2", callback_data="b2"),
                ]
            ]
        )

        self.assertEqual(len(keyboard.inline_keyboard), 1)
        self.assertEqual(len(keyboard.inline_keyboard[0]), 2)

    def test_multiple_row_keyboard(self) -> None:
        """Test creating a keyboard with multiple rows."""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Row 1", callback_data="r1")],
                [InlineKeyboardButton(text="Row 2", callback_data="r2")],
            ]
        )

        self.assertEqual(len(keyboard.inline_keyboard), 2)

    def test_to_dict(self) -> None:
        """Test converting keyboard to dict for API."""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Done", callback_data="ack:123"),
                ]
            ]
        )

        result = keyboard.to_dict()

        self.assertIn("inline_keyboard", result)
        self.assertEqual(result["inline_keyboard"][0][0]["text"], "Done")
        self.assertEqual(result["inline_keyboard"][0][0]["callback_data"], "ack:123")
        # None values should be excluded (Telegram API rejects null)
        self.assertNotIn("url", result["inline_keyboard"][0][0])

    def test_to_dict_excludes_none_values(self) -> None:
        """Test that to_dict excludes None values for Telegram API compatibility."""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Callback", callback_data="data"),
                    InlineKeyboardButton(text="URL", url="https://example.com"),
                ]
            ]
        )

        result = keyboard.to_dict()

        # First button has callback_data but not url
        btn1 = result["inline_keyboard"][0][0]
        self.assertEqual(btn1["text"], "Callback")
        self.assertEqual(btn1["callback_data"], "data")
        self.assertNotIn("url", btn1)

        # Second button has url but not callback_data
        btn2 = result["inline_keyboard"][0][1]
        self.assertEqual(btn2["text"], "URL")
        self.assertEqual(btn2["url"], "https://example.com")
        self.assertNotIn("callback_data", btn2)


class TestCallbackQuery(unittest.TestCase):
    """Tests for CallbackQuery model."""

    def test_callback_query_basic(self) -> None:
        """Test creating a basic callback query."""
        query = CallbackQuery(
            id="query-123",
            data="remind:ack:abc",
        )

        self.assertEqual(query.id, "query-123")
        self.assertEqual(query.data, "remind:ack:abc")
        self.assertIsNone(query.from_user)
        self.assertIsNone(query.message)

    def test_callback_query_with_user(self) -> None:
        """Test callback query with from field."""
        data = {
            "id": "query-456",
            "from": {
                "id": 12345,
                "is_bot": False,
                "first_name": "Test",
            },
            "data": "remind:snooze:xyz:60",
        }

        query = CallbackQuery.model_validate(data)

        self.assertEqual(query.id, "query-456")
        self.assertIsNotNone(query.from_user)
        self.assertEqual(query.from_user.id, 12345)  # type: ignore[union-attr]
        self.assertEqual(query.data, "remind:snooze:xyz:60")

    def test_callback_query_with_message(self) -> None:
        """Test callback query with message."""
        data = {
            "id": "query-789",
            "data": "action:param",
            "message": {
                "message_id": 100,
                "date": 1234567890,
                "chat": {"id": 999, "type": "private"},
                "text": "Original message",
            },
        }

        query = CallbackQuery.model_validate(data)

        self.assertIsNotNone(query.message)
        self.assertEqual(query.message.message_id, 100)  # type: ignore[union-attr]
        self.assertEqual(query.message.text, "Original message")  # type: ignore[union-attr]


class TestTelegramUpdateWithCallback(unittest.TestCase):
    """Tests for TelegramUpdate with callback_query field."""

    def test_update_with_message(self) -> None:
        """Test update containing a message."""
        update = TelegramUpdate(
            update_id=123,
            message=TelegramMessageInfo(
                message_id=1,
                date=1234567890,
                chat=TelegramChat(id=12345, type="private"),
                text="Hello",
            ),
        )

        self.assertIsNotNone(update.message)
        self.assertIsNone(update.callback_query)

    def test_update_with_callback_query(self) -> None:
        """Test update containing a callback query."""
        update = TelegramUpdate(
            update_id=456,
            callback_query=CallbackQuery(
                id="cb-123",
                data="remind:ack:abc",
            ),
        )

        self.assertIsNone(update.message)
        self.assertIsNotNone(update.callback_query)
        self.assertEqual(update.callback_query.data, "remind:ack:abc")


if __name__ == "__main__":
    unittest.main()
