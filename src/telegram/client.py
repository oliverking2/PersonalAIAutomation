"""Telegram Bot API client for sending and receiving messages."""

import asyncio
import logging
from typing import Any

import httpx

from src.telegram.models import SendMessageResult, TelegramUpdate

logger = logging.getLogger(__name__)

# Default API timeout in seconds
DEFAULT_REQUEST_TIMEOUT = 30.0


class TelegramClientError(Exception):
    """Raised when Telegram API request fails."""

    pass


class TelegramClient:
    """Async client for interacting with the Telegram Bot API.

    Supports both sending messages and receiving updates via long polling.
    Uses httpx for async HTTP requests.
    """

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str | None = None,
        poll_timeout: int = 30,
    ) -> None:
        """Initialise the Telegram client.

        :param bot_token: Telegram bot token from @BotFather.
        :param chat_id: Default chat ID for sending messages. Can be overridden per-message.
        :param poll_timeout: Timeout in seconds for long polling.
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._poll_timeout = poll_timeout
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"
        self._client: httpx.AsyncClient | None = None
        logger.debug(f"TelegramClient initialised with poll_timeout={poll_timeout}s")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client.

        :returns: The httpx AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=DEFAULT_REQUEST_TIMEOUT)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.debug("TelegramClient HTTP client closed")

    @property
    def chat_id(self) -> str | None:
        """Get the configured chat ID."""
        return self._chat_id

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "HTML",
    ) -> SendMessageResult:
        """Send a text message to a chat.

        :param text: The message text to send.
        :param chat_id: Target chat ID. If not provided, uses the configured chat_id.
        :param parse_mode: Message parse mode (HTML or Markdown).
        :returns: Result containing message_id and chat_id.
        :raises TelegramClientError: If the API request fails.
        :raises ValueError: If no chat_id is provided or configured.
        """
        target_chat_id = chat_id or self._chat_id
        if not target_chat_id:
            raise ValueError(
                "No chat_id provided. Set TELEGRAM_CHAT_ID environment variable, "
                "pass chat_id to constructor, or provide chat_id parameter."
            )

        url = f"{self._base_url}/sendMessage"
        logger.info(f"Sending message to chat_id={target_chat_id}")
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            client = await self._get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()

            result: dict[str, Any] = response.json()
            if not result.get("ok"):
                error_description = result.get("description", "Unknown error")
                raise TelegramClientError(f"Telegram API returned error: {error_description}")

            message_data = result.get("result", {})
            message_id = message_data.get("message_id")
            response_chat_id = message_data.get("chat", {}).get("id")

            logger.info(
                f"Message sent successfully: message_id={message_id}, chat_id={target_chat_id}"
            )
            return SendMessageResult(message_id=message_id, chat_id=response_chat_id)

        except httpx.TimeoutException as e:
            raise TelegramClientError(
                f"Telegram API request timed out after {DEFAULT_REQUEST_TIMEOUT}s"
            ) from e
        except httpx.HTTPStatusError as e:
            raise TelegramClientError(
                f"Telegram API request failed with status {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise TelegramClientError(f"Telegram API request failed: {e}") from e

    async def get_updates(
        self,
        offset: int | None = None,
        timeout: int | None = None,
    ) -> list[TelegramUpdate]:
        """Get updates from Telegram using long polling.

        :param offset: Identifier of the first update to be returned.
            Should be one greater than the highest update_id received.
        :param timeout: Timeout in seconds for long polling. If not provided,
            uses the configured poll_timeout.
        :returns: List of updates from Telegram.
        :raises TelegramClientError: If the API request fails.
        """
        url = f"{self._base_url}/getUpdates"
        poll_timeout = timeout if timeout is not None else self._poll_timeout

        params: dict[str, int] = {"timeout": poll_timeout}
        if offset is not None:
            params["offset"] = offset

        # Request timeout should be slightly longer than poll timeout
        # to avoid premature connection termination
        request_timeout = float(poll_timeout + 10)

        logger.debug(f"Polling for updates: offset={offset}, timeout={poll_timeout}s")

        try:
            client = await self._get_client()
            response = await client.get(url, params=params, timeout=request_timeout)
            response.raise_for_status()

            result: dict[str, Any] = response.json()
            if not result.get("ok"):
                error_description = result.get("description", "Unknown error")
                raise TelegramClientError(f"Telegram API returned error: {error_description}")

            updates_data = result.get("result", [])
            updates = [TelegramUpdate.model_validate(u) for u in updates_data]

            if updates:
                logger.debug(f"Received {len(updates)} updates")

            return updates

        except httpx.TimeoutException as e:
            # Timeout during long polling is normal - raise error for caller to handle
            logger.debug("Long poll timed out, no updates")
            raise TelegramClientError(
                f"Telegram API request timed out after {request_timeout}s"
            ) from e
        except httpx.HTTPStatusError as e:
            raise TelegramClientError(
                f"Telegram API request failed with status {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise TelegramClientError(f"Telegram API request failed: {e}") from e

    async def send_chat_action(
        self,
        action: str = "typing",
        chat_id: str | None = None,
    ) -> None:
        """Send a chat action (e.g., typing indicator) to a chat.

        The action automatically expires after 5 seconds or when a message
        is sent, whichever comes first.

        :param action: The action to send. Common values: "typing", "upload_document".
        :param chat_id: Target chat ID. If not provided, uses the configured chat_id.
        :raises TelegramClientError: If the API request fails.
        :raises ValueError: If no chat_id is provided or configured.
        """
        target_chat_id = chat_id or self._chat_id
        if not target_chat_id:
            raise ValueError(
                "No chat_id provided. Set TELEGRAM_CHAT_ID environment variable, "
                "pass chat_id to constructor, or provide chat_id parameter."
            )

        url = f"{self._base_url}/sendChatAction"
        payload = {
            "chat_id": target_chat_id,
            "action": action,
        }

        try:
            client = await self._get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()

            result: dict[str, Any] = response.json()
            if not result.get("ok"):
                error_description = result.get("description", "Unknown error")
                raise TelegramClientError(f"Telegram API returned error: {error_description}")

            logger.debug(f"Sent chat action '{action}' to chat_id={target_chat_id}")

        except httpx.TimeoutException as e:
            raise TelegramClientError(
                f"Telegram API request timed out after {DEFAULT_REQUEST_TIMEOUT}s"
            ) from e
        except httpx.HTTPStatusError as e:
            raise TelegramClientError(
                f"Telegram API request failed with status {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise TelegramClientError(f"Telegram API request failed: {e}") from e

    def send_message_sync(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "HTML",
    ) -> SendMessageResult:
        """Send a text message to a chat (synchronous wrapper).

        Use this method when calling from synchronous code like Dagster ops.
        For async code, use send_message() directly.

        :param text: The message text to send.
        :param chat_id: Target chat ID. If not provided, uses the configured chat_id.
        :param parse_mode: Message parse mode (HTML or Markdown).
        :returns: Result containing message_id and chat_id.
        :raises TelegramClientError: If the API request fails.
        :raises ValueError: If no chat_id is provided or configured.
        """
        return asyncio.run(self.send_message(text, chat_id, parse_mode))
