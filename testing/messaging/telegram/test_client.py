"""Tests for Telegram client module."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.messaging.telegram.client import (
    TelegramClient,
    TelegramClientError,
)


class TestTelegramClientInitialisation(unittest.TestCase):
    """Tests for TelegramClient initialisation."""

    def test_initialisation_with_all_parameters(self) -> None:
        """Test successful initialisation with all parameters."""
        client = TelegramClient(bot_token="test-token", chat_id="12345")

        self.assertEqual(client._bot_token, "test-token")
        self.assertEqual(client._chat_id, "12345")
        self.assertIn("test-token", client._base_url)

    def test_initialisation_without_chat_id_succeeds(self) -> None:
        """Test initialisation succeeds without chat_id (for receive-only usage)."""
        client = TelegramClient(bot_token="test-token")

        self.assertEqual(client._bot_token, "test-token")
        self.assertIsNone(client._chat_id)

    def test_poll_timeout_configuration(self) -> None:
        """Test that poll_timeout can be configured."""
        client = TelegramClient(bot_token="test-token", poll_timeout=60)

        self.assertEqual(client._poll_timeout, 60)

    def test_default_poll_timeout(self) -> None:
        """Test that default poll timeout is used when not specified."""
        client = TelegramClient(bot_token="test-token")

        self.assertEqual(client._poll_timeout, 30)


class TestTelegramClientSendMessage(unittest.IsolatedAsyncioTestCase):
    """Tests for TelegramClient.send_message method."""

    async def test_send_message_success(self) -> None:
        """Test successful message sending returns SendMessageResult."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123, "chat": {"id": 12345}},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            result = await client.send_message("Hello, World!")

            self.assertEqual(result.message_id, 123)
            self.assertEqual(result.chat_id, 12345)
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["chat_id"], "12345")
            self.assertEqual(call_kwargs["json"]["text"], "Hello, World!")
            self.assertEqual(call_kwargs["json"]["parse_mode"], "HTML")

    async def test_send_message_with_explicit_chat_id(self) -> None:
        """Test sending message to explicit chat_id parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 456, "chat": {"id": 99999}},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            result = await client.send_message("Hello!", chat_id="99999")

            self.assertEqual(result.chat_id, 99999)
            call_kwargs = mock_client.post.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["chat_id"], "99999")

    async def test_send_message_without_chat_id_raises_value_error(self) -> None:
        """Test sending message without any chat_id raises ValueError."""
        client = TelegramClient(bot_token="test-token")

        with self.assertRaises(ValueError) as context:
            await client.send_message("Test message")

        self.assertIn("chat_id", str(context.exception).lower())

    async def test_send_message_api_error_raises_exception(self) -> None:
        """Test that API error response raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                await client.send_message("Test message")

            self.assertIn("chat not found", str(context.exception))

    async def test_send_message_http_error_raises_exception(self) -> None:
        """Test that HTTP error raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                await client.send_message("Test message")

            self.assertIn("401", str(context.exception))

    async def test_send_message_timeout_raises_exception(self) -> None:
        """Test that timeout raises TelegramClientError."""
        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                await client.send_message("Test message")

            self.assertIn("timed out", str(context.exception).lower())

    async def test_send_message_connection_error_raises_exception(self) -> None:
        """Test that connection error raises TelegramClientError."""
        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                await client.send_message("Test message")

            self.assertIn("request failed", str(context.exception).lower())

    async def test_send_message_disables_web_page_preview(self) -> None:
        """Test that web page preview is disabled in messages."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 1, "chat": {"id": 12345}},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            await client.send_message("Check out https://example.com")

            call_kwargs = mock_client.post.call_args.kwargs
            self.assertTrue(call_kwargs["json"]["disable_web_page_preview"])


class TestTelegramClientGetUpdates(unittest.IsolatedAsyncioTestCase):
    """Tests for TelegramClient.get_updates method."""

    async def test_get_updates_success(self) -> None:
        """Test successful retrieval of updates."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {
                    "update_id": 123,
                    "message": {
                        "message_id": 1,
                        "date": 1234567890,
                        "chat": {"id": 12345, "type": "private"},
                        "from": {
                            "id": 67890,
                            "is_bot": False,
                            "first_name": "Test",
                        },
                        "text": "Hello",
                    },
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token")
            updates = await client.get_updates(offset=100)

            self.assertEqual(len(updates), 1)
            self.assertEqual(updates[0].update_id, 123)
            self.assertIsNotNone(updates[0].message)
            self.assertEqual(updates[0].message.text, "Hello")

            call_kwargs = mock_client.get.call_args.kwargs
            self.assertEqual(call_kwargs["params"]["offset"], 100)
            self.assertEqual(call_kwargs["params"]["timeout"], 30)  # Default poll timeout

    async def test_get_updates_empty(self) -> None:
        """Test get_updates with no updates."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": []}
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token")
            updates = await client.get_updates()

            self.assertEqual(len(updates), 0)

    async def test_get_updates_custom_timeout(self) -> None:
        """Test get_updates with custom timeout."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": []}
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", poll_timeout=60)
            await client.get_updates(timeout=45)

            call_kwargs = mock_client.get.call_args.kwargs
            self.assertEqual(call_kwargs["params"]["timeout"], 45)
            # Request timeout should be poll_timeout + 10
            self.assertEqual(call_kwargs["timeout"], 55.0)

    async def test_get_updates_api_error(self) -> None:
        """Test get_updates handles API error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "description": "Unauthorized",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token")

            with self.assertRaises(TelegramClientError) as context:
                await client.get_updates()

            self.assertIn("Unauthorized", str(context.exception))

    async def test_get_updates_timeout_raises_error(self) -> None:
        """Test get_updates raises error on timeout."""
        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token")

            with self.assertRaises(TelegramClientError) as context:
                await client.get_updates()

            self.assertIn("timed out", str(context.exception).lower())


class TestTelegramClientSendChatAction(unittest.IsolatedAsyncioTestCase):
    """Tests for TelegramClient.send_chat_action method."""

    async def test_send_chat_action_success(self) -> None:
        """Test successful sending of chat action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            await client.send_chat_action()

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["chat_id"], "12345")
            self.assertEqual(call_kwargs["json"]["action"], "typing")

    async def test_send_chat_action_with_explicit_chat_id(self) -> None:
        """Test sending chat action to explicit chat_id parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            await client.send_chat_action(chat_id="99999")

            call_kwargs = mock_client.post.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["chat_id"], "99999")

    async def test_send_chat_action_custom_action(self) -> None:
        """Test sending custom chat action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": True}
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            await client.send_chat_action(action="upload_document")

            call_kwargs = mock_client.post.call_args.kwargs
            self.assertEqual(call_kwargs["json"]["action"], "upload_document")

    async def test_send_chat_action_without_chat_id_raises_value_error(self) -> None:
        """Test sending chat action without any chat_id raises ValueError."""
        client = TelegramClient(bot_token="test-token")

        with self.assertRaises(ValueError) as context:
            await client.send_chat_action()

        self.assertIn("chat_id", str(context.exception).lower())

    async def test_send_chat_action_api_error_raises_exception(self) -> None:
        """Test that API error response raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                await client.send_chat_action()

            self.assertIn("chat not found", str(context.exception))

    async def test_send_chat_action_timeout_raises_exception(self) -> None:
        """Test that timeout raises TelegramClientError."""
        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                await client.send_chat_action()

            self.assertIn("timed out", str(context.exception).lower())


class TestTelegramClientSendMessageSync(unittest.TestCase):
    """Tests for TelegramClient.send_message_sync method."""

    def test_send_message_sync_success(self) -> None:
        """Test successful synchronous message sending."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123, "chat": {"id": 12345}},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")
            result = client.send_message_sync("Hello, World!")

            self.assertEqual(result.message_id, 123)
            self.assertEqual(result.chat_id, 12345)

    def test_send_message_sync_without_chat_id_raises_value_error(self) -> None:
        """Test sending message without any chat_id raises ValueError."""
        client = TelegramClient(bot_token="test-token")

        with self.assertRaises(ValueError) as context:
            client.send_message_sync("Test message")

        self.assertIn("chat_id", str(context.exception).lower())

    def test_send_message_sync_api_error_raises_exception(self) -> None:
        """Test that API error response raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                client.send_message_sync("Test message")

            self.assertIn("chat not found", str(context.exception))

    def test_send_message_sync_timeout_raises_exception(self) -> None:
        """Test that timeout raises TelegramClientError."""
        with patch("src.messaging.telegram.client.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                client.send_message_sync("Test message")

            self.assertIn("timed out", str(context.exception).lower())

    def test_send_message_sync_http_error_raises_exception(self) -> None:
        """Test that HTTP error raises TelegramClientError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("src.messaging.telegram.client.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            with self.assertRaises(TelegramClientError) as context:
                client.send_message_sync("Test message")

            self.assertIn("401", str(context.exception))

    def test_send_message_sync_can_be_called_multiple_times(self) -> None:
        """Test that send_message_sync can be called multiple times without errors.

        This is a regression test for the event loop issue where asyncio.run()
        would fail on subsequent calls.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 1, "chat": {"id": 12345}},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.messaging.telegram.client.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token", chat_id="12345")

            # Call multiple times - this should not raise
            for i in range(3):
                result = client.send_message_sync(f"Message {i}")
                self.assertEqual(result.message_id, 1)


class TestTelegramClientClose(unittest.IsolatedAsyncioTestCase):
    """Tests for TelegramClient.close method."""

    async def test_close_client(self) -> None:
        """Test closing the HTTP client."""
        with patch("src.messaging.telegram.client.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client

            client = TelegramClient(bot_token="test-token")
            # Trigger client creation
            await client._get_client()

            # Close the client
            await client.close()

            mock_client.aclose.assert_called_once()

    async def test_close_client_when_already_closed(self) -> None:
        """Test closing client when already closed does nothing."""
        client = TelegramClient(bot_token="test-token")
        # Client not created yet, should not raise
        await client.close()


if __name__ == "__main__":
    unittest.main()
