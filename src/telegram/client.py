"""Telegram Bot API client for sending messages."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

# Telegram API timeout in seconds
REQUEST_TIMEOUT = 30


class TelegramClientError(Exception):
    """Raised when Telegram API request fails."""

    pass


class TelegramClient:
    """Client for interacting with the Telegram Bot API."""

    def __init__(
        self,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        """Initialise the Telegram client.

        :param bot_token: Telegram bot token. If not provided, reads from
            TELEGRAM_BOT_TOKEN environment variable.
        :param chat_id: Target chat ID. If not provided, reads from
            TELEGRAM_CHAT_ID environment variable.
        :raises ValueError: If bot_token or chat_id is not provided and not
            found in environment.
        """
        self._bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

        if not self._bot_token:
            raise ValueError(
                "Telegram bot token not provided. Set TELEGRAM_BOT_TOKEN environment "
                "variable or pass bot_token parameter."
            )
        if not self._chat_id:
            raise ValueError(
                "Telegram chat ID not provided. Set TELEGRAM_CHAT_ID environment "
                "variable or pass chat_id parameter."
            )

        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"
        logger.debug(f"TelegramClient initialised for chat_id={self._chat_id}")

    def send_message(self, text: str) -> bool:
        """Send a text message to the configured chat.

        :param text: The message text to send.
        :returns: True if the message was sent successfully.
        :raises TelegramClientError: If the API request fails.
        """
        url = f"{self._base_url}/sendMessage"
        logger.info(f"Sending message to chat_id={self._chat_id}")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                error_description = result.get("description", "Unknown error")
                raise TelegramClientError(f"Telegram API returned error: {error_description}")

            logger.info(f"Message sent successfully to chat_id={self._chat_id}")
            return True

        except requests.exceptions.Timeout as e:
            raise TelegramClientError(
                f"Telegram API request timed out after {REQUEST_TIMEOUT}s"
            ) from e
        except requests.exceptions.RequestException as e:
            raise TelegramClientError(f"Telegram API request failed: {e}") from e
