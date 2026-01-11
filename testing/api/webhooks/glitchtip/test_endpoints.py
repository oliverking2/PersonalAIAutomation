"""Tests for GlitchTip webhook endpoints."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.messaging.telegram.client import TelegramClientError


class TestGlitchTipWebhook(unittest.TestCase):
    """Tests for the GlitchTip webhook endpoint."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.valid_token = "test-webhook-secret"
        self.sample_alert = {
            "alias": "production",
            "text": "New error in production",
            "attachments": [
                {
                    "title": "ValueError: Invalid input",
                    "title_link": "https://glitchtip.example.com/issues/123",
                    "text": "Traceback...",
                    "color": "#ff0000",
                    "fields": [
                        {"title": "project", "value": "my-app", "short": True},
                        {"title": "environment", "value": "production", "short": True},
                    ],
                }
            ],
        }

    @patch("src.api.webhooks.glitchtip.endpoints._get_telegram_client")
    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_success(self, mock_get_secret: MagicMock, mock_get_client: MagicMock) -> None:
        """Test successful webhook processing."""
        mock_get_secret.return_value = self.valid_token
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        response = self.client.post(
            f"/webhooks/glitchtip?token={self.valid_token}",
            json=self.sample_alert,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("forwarded", data["message"].lower())
        mock_client.send_message_sync.assert_called_once()

    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_missing_token(self, mock_get_secret: MagicMock) -> None:
        """Test webhook rejects requests without token."""
        mock_get_secret.return_value = self.valid_token

        response = self.client.post(
            "/webhooks/glitchtip",
            json=self.sample_alert,
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Missing", response.json()["detail"])

    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_invalid_token(self, mock_get_secret: MagicMock) -> None:
        """Test webhook rejects requests with invalid token."""
        mock_get_secret.return_value = self.valid_token

        response = self.client.post(
            "/webhooks/glitchtip?token=wrong-token",
            json=self.sample_alert,
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid", response.json()["detail"])

    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_secret_not_configured(self, mock_get_secret: MagicMock) -> None:
        """Test webhook handles missing secret configuration."""
        mock_get_secret.side_effect = ValueError("GLITCHTIP_WEBHOOK_SECRET not configured")

        response = self.client.post(
            "/webhooks/glitchtip?token=any-token",
            json=self.sample_alert,
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("not configured", response.json()["detail"])

    @patch("src.api.webhooks.glitchtip.endpoints._get_telegram_client")
    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_telegram_not_configured(
        self, mock_get_secret: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Test webhook handles missing Telegram configuration."""
        mock_get_secret.return_value = self.valid_token
        mock_get_client.side_effect = ValueError("TELEGRAM_BOT_TOKEN not configured")

        response = self.client.post(
            f"/webhooks/glitchtip?token={self.valid_token}",
            json=self.sample_alert,
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("Telegram not configured", response.json()["detail"])

    @patch("src.api.webhooks.glitchtip.endpoints._get_telegram_client")
    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_telegram_send_fails(
        self, mock_get_secret: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Test webhook handles Telegram send failure."""
        mock_get_secret.return_value = self.valid_token
        mock_client = MagicMock()
        mock_client.send_message_sync.side_effect = TelegramClientError("Send failed")
        mock_get_client.return_value = mock_client

        response = self.client.post(
            f"/webhooks/glitchtip?token={self.valid_token}",
            json=self.sample_alert,
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("Failed to send", response.json()["detail"])

    @patch("src.api.webhooks.glitchtip.endpoints._get_telegram_client")
    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_webhook_empty_alert(
        self, mock_get_secret: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Test webhook handles empty alert payload."""
        mock_get_secret.return_value = self.valid_token
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        response = self.client.post(
            f"/webhooks/glitchtip?token={self.valid_token}",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        mock_client.send_message_sync.assert_called_once()


class TestGlitchTipTestEndpoint(unittest.TestCase):
    """Tests for the GlitchTip test alert endpoint."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.valid_token = "test-webhook-secret"

    @patch("src.api.webhooks.glitchtip.endpoints._get_telegram_client")
    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_test_endpoint_success(
        self, mock_get_secret: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Test successful test alert."""
        mock_get_secret.return_value = self.valid_token
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        response = self.client.post(
            f"/webhooks/glitchtip/test?token={self.valid_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("test", data["message"].lower())
        mock_client.send_message_sync.assert_called_once()

        # Verify the message contains test alert content
        call_args = mock_client.send_message_sync.call_args
        message = call_args[0][0]
        self.assertIn("Test Error Alert", message)

    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_test_endpoint_requires_auth(self, mock_get_secret: MagicMock) -> None:
        """Test that test endpoint requires authentication."""
        mock_get_secret.return_value = self.valid_token

        response = self.client.post("/webhooks/glitchtip/test")

        self.assertEqual(response.status_code, 401)

    @patch("src.api.webhooks.glitchtip.endpoints._get_webhook_secret")
    def test_test_endpoint_invalid_token(self, mock_get_secret: MagicMock) -> None:
        """Test that test endpoint rejects invalid token."""
        mock_get_secret.return_value = self.valid_token

        response = self.client.post("/webhooks/glitchtip/test?token=wrong")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
