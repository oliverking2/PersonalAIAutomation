"""Tests for GlitchTip webhook models."""

import unittest

from src.api.webhooks.glitchtip.models import (
    GlitchTipAlert,
    GlitchTipAttachment,
    GlitchTipField,
    WebhookResponse,
)


class TestGlitchTipField(unittest.TestCase):
    """Tests for GlitchTipField model."""

    def test_parse_field(self) -> None:
        """Test parsing a field from dict."""
        data = {"title": "project", "value": "my-project", "short": True}
        field = GlitchTipField.model_validate(data)

        self.assertEqual(field.title, "project")
        self.assertEqual(field.value, "my-project")
        self.assertTrue(field.short)

    def test_short_defaults_to_true(self) -> None:
        """Test that short defaults to True if not provided."""
        data = {"title": "environment", "value": "production"}
        field = GlitchTipField.model_validate(data)

        self.assertTrue(field.short)

    def test_extra_fields_ignored(self) -> None:
        """Test that extra fields are ignored."""
        data = {
            "title": "project",
            "value": "my-project",
            "short": True,
            "unknown_field": "should be ignored",
        }
        field = GlitchTipField.model_validate(data)

        self.assertEqual(field.title, "project")
        self.assertFalse(hasattr(field, "unknown_field"))


class TestGlitchTipAttachment(unittest.TestCase):
    """Tests for GlitchTipAttachment model."""

    def test_parse_full_attachment(self) -> None:
        """Test parsing a complete attachment."""
        data = {
            "title": "ValueError: Something went wrong",
            "title_link": "https://glitchtip.example.com/issues/123",
            "text": "Traceback (most recent call last)...",
            "color": "#ff0000",
            "fields": [
                {"title": "project", "value": "my-app", "short": True},
                {"title": "environment", "value": "production", "short": True},
            ],
        }
        attachment = GlitchTipAttachment.model_validate(data)

        self.assertEqual(attachment.title, "ValueError: Something went wrong")
        self.assertEqual(attachment.title_link, "https://glitchtip.example.com/issues/123")
        self.assertEqual(attachment.text, "Traceback (most recent call last)...")
        self.assertEqual(attachment.color, "#ff0000")
        self.assertEqual(len(attachment.fields), 2)

    def test_parse_minimal_attachment(self) -> None:
        """Test parsing an attachment with only required fields."""
        data = {"title": "Error occurred"}
        attachment = GlitchTipAttachment.model_validate(data)

        self.assertEqual(attachment.title, "Error occurred")
        self.assertIsNone(attachment.title_link)
        self.assertIsNone(attachment.text)
        self.assertIsNone(attachment.color)
        self.assertEqual(attachment.fields, [])

    def test_get_field_value_found(self) -> None:
        """Test getting a field value that exists."""
        data = {
            "title": "Error",
            "fields": [
                {"title": "project", "value": "my-app", "short": True},
                {"title": "environment", "value": "production", "short": True},
            ],
        }
        attachment = GlitchTipAttachment.model_validate(data)

        self.assertEqual(attachment.get_field_value("project"), "my-app")
        self.assertEqual(attachment.get_field_value("environment"), "production")

    def test_get_field_value_case_insensitive(self) -> None:
        """Test that field lookup is case-insensitive."""
        data = {
            "title": "Error",
            "fields": [{"title": "Project", "value": "my-app", "short": True}],
        }
        attachment = GlitchTipAttachment.model_validate(data)

        self.assertEqual(attachment.get_field_value("project"), "my-app")
        self.assertEqual(attachment.get_field_value("PROJECT"), "my-app")

    def test_get_field_value_not_found(self) -> None:
        """Test getting a field value that doesn't exist."""
        data = {"title": "Error", "fields": []}
        attachment = GlitchTipAttachment.model_validate(data)

        self.assertIsNone(attachment.get_field_value("nonexistent"))


class TestGlitchTipAlert(unittest.TestCase):
    """Tests for GlitchTipAlert model."""

    def test_parse_full_alert(self) -> None:
        """Test parsing a complete alert payload."""
        data = {
            "alias": "production-errors",
            "text": "New error in production",
            "attachments": [
                {
                    "title": "ValueError",
                    "title_link": "https://glitchtip.example.com/issues/1",
                    "text": "Stack trace...",
                    "color": "#ff0000",
                    "fields": [{"title": "project", "value": "app", "short": True}],
                }
            ],
        }
        alert = GlitchTipAlert.model_validate(data)

        self.assertEqual(alert.alias, "production-errors")
        self.assertEqual(alert.text, "New error in production")
        self.assertEqual(len(alert.attachments), 1)
        self.assertEqual(alert.attachments[0].title, "ValueError")

    def test_parse_minimal_alert(self) -> None:
        """Test parsing an alert with no optional fields."""
        data: dict[str, object] = {}
        alert = GlitchTipAlert.model_validate(data)

        self.assertIsNone(alert.alias)
        self.assertIsNone(alert.text)
        self.assertEqual(alert.attachments, [])

    def test_extra_fields_ignored(self) -> None:
        """Test that extra fields in the payload are ignored."""
        data = {
            "alias": "test",
            "unknown_field": "should be ignored",
            "another_unknown": 123,
        }
        alert = GlitchTipAlert.model_validate(data)

        self.assertEqual(alert.alias, "test")


class TestWebhookResponse(unittest.TestCase):
    """Tests for WebhookResponse model."""

    def test_create_response(self) -> None:
        """Test creating a webhook response."""
        response = WebhookResponse(status="ok", message="Alert processed")

        self.assertEqual(response.status, "ok")
        self.assertEqual(response.message, "Alert processed")

    def test_serialise_response(self) -> None:
        """Test serialising response to dict."""
        response = WebhookResponse(status="ok", message="Success")
        data = response.model_dump()

        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["message"], "Success")


if __name__ == "__main__":
    unittest.main()
