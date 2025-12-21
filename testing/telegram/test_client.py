"""Tests for Telegram client module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from src.telegram.client import REQUEST_TIMEOUT, TelegramClient, TelegramClientError


class TestTelegramClientInitialisation(unittest.TestCase):
    """Tests for TelegramClient initialisation."""

    @patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "12345"},
    )
    def test_initialisation_with_env_vars(self) -> None:
        """Test successful initialisation with environment variables."""
        client = TelegramClient()

        self.assertEqual(client._bot_token, "test-token")
        self.assertEqual(client._chat_id, "12345")
        self.assertIn("test-token", client._base_url)

    def test_initialisation_with_explicit_parameters(self) -> None:
        """Test successful initialisation with explicit parameters."""
        client = TelegramClient(bot_token="explicit-token", chat_id="67890")

        self.assertEqual(client._bot_token, "explicit-token")
        self.assertEqual(client._chat_id, "67890")

    @patch.dict("os.environ", {}, clear=True)
    def test_initialisation_missing_bot_token_raises_value_error(self) -> None:
        """Test initialisation fails when bot token is missing."""
        with self.assertRaises(ValueError) as context:
            TelegramClient()

        self.assertIn("bot token", str(context.exception).lower())

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token"}, clear=True)
    def test_initialisation_missing_chat_id_raises_value_error(self) -> None:
        """Test initialisation fails when chat ID is missing."""
        with self.assertRaises(ValueError) as context:
            TelegramClient()

        self.assertIn("chat ID", str(context.exception))

    @patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "env-token", "TELEGRAM_CHAT_ID": "env-chat"},
    )
    def test_explicit_parameters_override_env_vars(self) -> None:
        """Test that explicit parameters take precedence over environment variables."""
        client = TelegramClient(bot_token="explicit-token", chat_id="explicit-chat")

        self.assertEqual(client._bot_token, "explicit-token")
        self.assertEqual(client._chat_id, "explicit-chat")


class TestTelegramClientSendMessage(unittest.TestCase):
    """Tests for TelegramClient.send_message method."""

    @patch("src.telegram.client.requests.post")
    def test_send_message_success(self, mock_post: MagicMock) -> None:
        """Test successful message sending."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_post.return_value = mock_response

        client = TelegramClient(bot_token="test-token", chat_id="12345")
        result = client.send_message("Hello, World!")

        self.assertTrue(result)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["chat_id"], "12345")
        self.assertEqual(call_kwargs["json"]["text"], "Hello, World!")
        self.assertEqual(call_kwargs["json"]["parse_mode"], "HTML")
        self.assertEqual(call_kwargs["timeout"], REQUEST_TIMEOUT)

    @patch("src.telegram.client.requests.post")
    def test_send_message_api_error_raises_exception(self, mock_post: MagicMock) -> None:
        """Test that API error response raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = TelegramClient(bot_token="test-token", chat_id="12345")

        with self.assertRaises(TelegramClientError) as context:
            client.send_message("Test message")

        self.assertIn("chat not found", str(context.exception))

    @patch("src.telegram.client.requests.post")
    def test_send_message_http_error_raises_exception(self, mock_post: MagicMock) -> None:
        """Test that HTTP error raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )
        mock_post.return_value = mock_response

        client = TelegramClient(bot_token="test-token", chat_id="12345")

        with self.assertRaises(TelegramClientError) as context:
            client.send_message("Test message")

        self.assertIn("request failed", str(context.exception).lower())

    @patch("src.telegram.client.requests.post")
    def test_send_message_timeout_raises_exception(self, mock_post: MagicMock) -> None:
        """Test that timeout raises TelegramClientError."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        client = TelegramClient(bot_token="test-token", chat_id="12345")

        with self.assertRaises(TelegramClientError) as context:
            client.send_message("Test message")

        self.assertIn("timed out", str(context.exception).lower())

    @patch("src.telegram.client.requests.post")
    def test_send_message_connection_error_raises_exception(self, mock_post: MagicMock) -> None:
        """Test that connection error raises TelegramClientError."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        client = TelegramClient(bot_token="test-token", chat_id="12345")

        with self.assertRaises(TelegramClientError) as context:
            client.send_message("Test message")

        self.assertIn("request failed", str(context.exception).lower())

    @patch("src.telegram.client.requests.post")
    def test_send_message_disables_web_page_preview(self, mock_post: MagicMock) -> None:
        """Test that web page preview is disabled in messages."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        client = TelegramClient(bot_token="test-token", chat_id="12345")
        client.send_message("Check out https://example.com")

        call_kwargs = mock_post.call_args.kwargs
        self.assertTrue(call_kwargs["json"]["disable_web_page_preview"])


if __name__ == "__main__":
    unittest.main()
