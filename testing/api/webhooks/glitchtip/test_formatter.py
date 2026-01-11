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

        result = format_glitchtip_alert(alert)

        self.assertIn("🚨 <b>Error Alert</b>", result)
        self.assertIn("<b>ValueError: Invalid input</b>", result)
        self.assertIn("Traceback (most recent call last):", result)
        self.assertIn("📦 Project: my-app", result)
        self.assertIn("🌍 Environment: production", result)
        self.assertIn("🏷️ Release: v1.2.3", result)
        self.assertIn(
            '<a href="https://glitchtip.example.com/issues/123">View in GlitchTip</a>', result
        )

    def test_format_alert_without_optional_fields(self) -> None:
        """Test formatting an alert with minimal fields."""
        alert = GlitchTipAlert(
            attachments=[
                GlitchTipAttachment(
                    title="Error occurred",
                )
            ],
        )

        result = format_glitchtip_alert(alert)

        self.assertIn("🚨 <b>Error Alert</b>", result)
        self.assertIn("<b>Error occurred</b>", result)
        self.assertNotIn("📦 Project:", result)
        self.assertNotIn("🌍 Environment:", result)
        self.assertNotIn("🏷️ Release:", result)
        self.assertNotIn("View in GlitchTip", result)

    def test_format_alert_no_attachments(self) -> None:
        """Test formatting an alert with no attachments."""
        alert = GlitchTipAlert(text="Simple alert message")

        result = format_glitchtip_alert(alert)

        self.assertIn("🚨 <b>Error Alert</b>", result)
        self.assertIn("Simple alert message", result)

    def test_format_alert_empty(self) -> None:
        """Test formatting an empty alert."""
        alert = GlitchTipAlert()

        result = format_glitchtip_alert(alert)

        self.assertIn("🚨 <b>Error Alert</b>", result)

    def test_format_escapes_html(self) -> None:
        """Test that HTML in alert content is escaped."""
        alert = GlitchTipAlert(
            attachments=[
                GlitchTipAttachment(
                    title="<script>alert('xss')</script>",
                    text="<b>Bold</b> text",
                    fields=[
                        GlitchTipField(title="project", value="<project>", short=True),
                    ],
                )
            ],
        )

        result = format_glitchtip_alert(alert)

        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&lt;b&gt;Bold&lt;/b&gt;", result)
        self.assertIn("&lt;project&gt;", result)
        self.assertNotIn("<script>", result)

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

        result = format_glitchtip_alert(alert)

        # Should be truncated to 500 chars + "..."
        self.assertIn("...", result)
        self.assertLess(len(result), len(long_text) + 200)


class TestFormatTestAlert(unittest.TestCase):
    """Tests for format_test_alert function."""

    def test_format_test_alert(self) -> None:
        """Test generating a test alert message."""
        result = format_test_alert()

        self.assertIn("🧪 <b>Test Error Alert</b>", result)
        self.assertIn("GlitchTip Integration Test", result)
        self.assertIn("test alert to verify", result)
        self.assertIn("📦 Project: test-project", result)
        self.assertIn("🌍 Environment: test", result)
        self.assertIn("integration is working correctly", result)


if __name__ == "__main__":
    unittest.main()
