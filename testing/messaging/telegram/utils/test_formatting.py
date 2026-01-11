"""Tests for Telegram formatting utilities."""

import unittest

from src.messaging.telegram.utils.formatting import (
    MessageFormatter,
    TelegramFormatter,
    format_message,
    get_formatter,
)


class TestMessageFormatterInterface(unittest.TestCase):
    """Tests for MessageFormatter ABC."""

    def test_telegram_formatter_is_message_formatter(self) -> None:
        """Test that TelegramFormatter implements MessageFormatter."""
        formatter = TelegramFormatter()
        self.assertIsInstance(formatter, MessageFormatter)

    def test_get_formatter_returns_message_formatter(self) -> None:
        """Test that get_formatter returns a MessageFormatter instance."""
        formatter = get_formatter()
        self.assertIsInstance(formatter, MessageFormatter)


class TestTelegramFormatter(unittest.TestCase):
    """Tests for TelegramFormatter."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.formatter = TelegramFormatter()

    def test_returns_tuple(self) -> None:
        """Test that format returns a tuple."""
        result = self.formatter.format("Hello")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_returns_markdownv2_parse_mode(self) -> None:
        """Test that format returns MarkdownV2 parse mode."""
        _, parse_mode = self.formatter.format("Hello")
        self.assertEqual(parse_mode, "MarkdownV2")

    def test_plain_text(self) -> None:
        """Test formatting plain text."""
        formatted, _ = self.formatter.format("Hello world")
        self.assertIsInstance(formatted, str)
        self.assertIn("Hello", formatted)

    def test_bold_formatting(self) -> None:
        """Test bold formatting is preserved."""
        formatted, _ = self.formatter.format("Hello **bold** world")
        # telegramify-markdown converts **bold** to *bold* for MarkdownV2
        self.assertIn("bold", formatted)

    def test_italic_formatting(self) -> None:
        """Test italic formatting is preserved."""
        formatted, _ = self.formatter.format("Hello *italic* world")
        self.assertIn("italic", formatted)

    def test_empty_string(self) -> None:
        """Test formatting empty string."""
        formatted, parse_mode = self.formatter.format("")
        self.assertEqual(formatted, "")
        self.assertEqual(parse_mode, "MarkdownV2")


class TestFormatMessage(unittest.TestCase):
    """Tests for format_message convenience function."""

    def test_returns_tuple(self) -> None:
        """Test that format_message returns a tuple."""
        result = format_message("Hello")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_returns_markdownv2_parse_mode(self) -> None:
        """Test that format_message returns MarkdownV2 parse mode."""
        _, parse_mode = format_message("Hello")
        self.assertEqual(parse_mode, "MarkdownV2")

    def test_formats_agent_response(self) -> None:
        """Test formatting typical agent response."""
        text = """Done! I've created 3 test ideas for you:

1. **Test - Example Idea One** - with notes
2. **Test - Example Idea Two** - with notes"""

        formatted, parse_mode = format_message(text)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Test", formatted)
        self.assertIn("Example Idea One", formatted)

    def test_formats_reminder_response(self) -> None:
        """Test formatting reminder-style response."""
        text = """Yes, I can create both **reminders** and **ideas**!

## Reminders

I can create:
- **One-time reminders** - trigger at a specific date/time
- **Recurring reminders** - repeat on a schedule"""

        formatted, parse_mode = format_message(text)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("reminders", formatted)
        self.assertIn("ideas", formatted)


if __name__ == "__main__":
    unittest.main()
