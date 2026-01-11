"""Tests for GlitchTip alert formatter."""

import unittest

from src.api.webhooks.glitchtip.formatter import (
    format_glitchtip_alert,
    format_test_alert,
)
from src.api.webhooks.glitchtip.models import (
    GlitchTipAlert,
    GlitchTipAttachment,
    GlitchTipField,
)


class TestFormatGlitchTipAlert(unittest.TestCase):
    """Tests for format_glitchtip_alert function."""

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that formatter returns (text, parse_mode) tuple."""
        alert = GlitchTipAlert()

        result = format_glitchtip_alert(alert)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIsInstance(text, str)

    def test_format_full_alert(self) -> None:
        """Test formatting an alert with all fields."""
        alert = GlitchTipAlert(
            text="New error",
            attachments=[
                GlitchTipAttachment(
                    title="ValueError: Invalid input",
                    title_link="https://glitchtip.example.com/issues/123",
                    text="Traceback (most recent call last):\n  File...",
                    color="#ff0000",
                    fields=[
                        GlitchTipField(title="project", value="my-app", short=True),
                        GlitchTipField(title="environment", value="production", short=True),
                        GlitchTipField(title="release", value="v1.2.3", short=True),
                    ],
                )
            ],
        )

        text, parse_mode = format_glitchtip_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Error Alert", text)
        self.assertIn("ValueError", text)
        self.assertIn("Traceback", text)
        self.assertIn("Project", text)
        self.assertIn("Environment", text)
        self.assertIn("Release", text)
        self.assertIn("View in GlitchTip", text)

    def test_format_alert_without_optional_fields(self) -> None:
        """Test formatting an alert with minimal fields."""
        alert = GlitchTipAlert(
            attachments=[
                GlitchTipAttachment(
                    title="Error occurred",
                )
            ],
        )

        text, parse_mode = format_glitchtip_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Error Alert", text)
        self.assertIn("Error occurred", text)
        self.assertNotIn("Project", text)
        self.assertNotIn("Environment", text)
        self.assertNotIn("View in GlitchTip", text)

    def test_format_alert_no_attachments(self) -> None:
        """Test formatting an alert with no attachments."""
        alert = GlitchTipAlert(text="Simple alert message")

        text, parse_mode = format_glitchtip_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Error Alert", text)
        self.assertIn("Simple alert message", text)

    def test_format_alert_empty(self) -> None:
        """Test formatting an empty alert."""
        alert = GlitchTipAlert()

        text, parse_mode = format_glitchtip_alert(alert)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Error Alert", text)

    def test_format_truncates_long_text(self) -> None:
        """Test that long error text is truncated."""
        long_text = "x" * 1000
        alert = GlitchTipAlert(
            attachments=[
                GlitchTipAttachment(
                    title="Error",
                    text=long_text,
                )
            ],
        )

        text, _parse_mode = format_glitchtip_alert(alert)

        # Should be truncated (output will be shorter than input)
        self.assertLess(len(text), len(long_text))


class TestFormatTestAlert(unittest.TestCase):
    """Tests for format_test_alert function."""

    def test_returns_tuple_with_parse_mode(self) -> None:
        """Test that formatter returns (text, parse_mode) tuple."""
        result = format_test_alert()

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        _text, parse_mode = result
        self.assertEqual(parse_mode, "MarkdownV2")

    def test_format_test_alert(self) -> None:
        """Test generating a test alert message."""
        text, parse_mode = format_test_alert()

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Test Error Alert", text)
        self.assertIn("GlitchTip Integration Test", text)
        self.assertIn("test alert to verify", text)
        self.assertIn("Project", text)
        self.assertIn("Environment", text)
        self.assertIn("integration is working correctly", text)


if __name__ == "__main__":
    unittest.main()
