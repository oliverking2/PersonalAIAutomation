"""Long polling runner for Telegram bot."""

from __future__ import annotations

import logging
import signal
import time
from types import FrameType
from typing import TYPE_CHECKING

from src.database.connection import get_session
from src.database.telegram import get_or_create_polling_cursor, update_polling_cursor
from src.telegram.client import TelegramClient, TelegramClientError
from src.telegram.handler import MessageHandler, UnauthorisedChatError
from src.telegram.models import TelegramUpdate
from src.telegram.utils.config import TelegramConfig, get_telegram_settings
from src.telegram.utils.session_manager import SessionManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PollingRunner:
    """Long polling runner for receiving Telegram updates.

    Runs a continuous loop that:
    1. Polls Telegram for updates using long polling
    2. Delegates updates to the MessageHandler
    3. Persists the polling offset
    4. Handles graceful shutdown on SIGINT/SIGTERM
    """

    def __init__(
        self,
        client: TelegramClient | None = None,
        settings: TelegramConfig | None = None,
        handler: MessageHandler | None = None,
    ) -> None:
        """Initialise the polling runner.

        :param client: Telegram client. If not provided, creates one from env.
        :param settings: Telegram settings. If not provided, loads from env.
        :param handler: Message handler. If not provided, creates default one.
        """
        self._settings = settings or get_telegram_settings()
        self._client = client or TelegramClient(poll_timeout=self._settings.poll_timeout)
        self._session_manager = SessionManager(
            session_timeout_minutes=self._settings.session_timeout_minutes
        )
        self._handler = handler or MessageHandler(
            settings=self._settings,
            session_manager=self._session_manager,
        )
        self._running = False
        self._consecutive_errors = 0

    def run(self) -> None:
        """Start the polling loop.

        Blocks until shutdown signal is received.
        """
        self._running = True
        self._setup_signal_handlers()

        logger.info(
            f"Starting Telegram polling runner: poll_timeout={self._settings.poll_timeout}s, "
            f"session_timeout={self._settings.session_timeout_minutes}min"
        )

        try:
            self._polling_loop()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            logger.info("Polling runner stopped")

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        logger.info("Stopping polling runner...")
        self._running = False

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: FrameType | None) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown")
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _polling_loop(self) -> None:
        """Execute the main polling loop."""
        # Get initial offset from database
        with get_session() as db_session:
            cursor = get_or_create_polling_cursor(db_session)
            offset = cursor.last_update_id + 1 if cursor.last_update_id > 0 else None

        logger.info(f"Starting polling from offset={offset}")

        while self._running:
            try:
                updates = self._client.get_updates(offset=offset)
                self._consecutive_errors = 0  # Reset on success

                for update in updates:
                    self._process_update(update)
                    # Update offset after each successful processing
                    offset = update.update_id + 1

                    # Persist offset to database
                    with get_session() as db_session:
                        update_polling_cursor(db_session, update.update_id)

            except TelegramClientError as e:
                self._handle_polling_error(e)

    def _process_update(self, update: TelegramUpdate) -> None:
        """Process a single update.

        :param update: The Telegram update to process.
        """
        try:
            with get_session() as db_session:
                response = self._handler.handle_update(db_session, update)

                if response:
                    # Send response back to the chat
                    chat_id = str(update.message.chat.id) if update.message else None
                    if chat_id:
                        self._send_response(chat_id, response)

        except UnauthorisedChatError as e:
            logger.warning(f"Ignored message from unauthorised chat: {e.chat_id}")
        except Exception:
            logger.exception(f"Error processing update: update_id={update.update_id}")
            # Try to send error message to user
            if update.message:
                chat_id = str(update.message.chat.id)
                self._send_error_response(chat_id)

    def _send_response(self, chat_id: str, text: str) -> None:
        """Send a response message to a chat.

        :param chat_id: Target chat ID.
        :param text: Response text.
        """
        try:
            self._client.send_message(text, chat_id=chat_id, parse_mode="")
            logger.debug(f"Sent response to chat_id={chat_id}")
        except TelegramClientError:
            logger.exception(f"Failed to send response to chat_id={chat_id}")

    def _send_error_response(self, chat_id: str) -> None:
        """Send a generic error response to a chat.

        :param chat_id: Target chat ID.
        """
        try:
            self._client.send_message(
                "Sorry, I encountered an error. Please try again.",
                chat_id=chat_id,
                parse_mode="",
            )
        except TelegramClientError:
            logger.exception(f"Failed to send error response to chat_id={chat_id}")

    def _handle_polling_error(self, error: TelegramClientError) -> None:
        """Handle an error during polling.

        Implements exponential backoff for consecutive errors.

        :param error: The error that occurred.
        """
        self._consecutive_errors += 1
        logger.warning(f"Polling error (consecutive: {self._consecutive_errors}): {error}")

        if self._consecutive_errors >= self._settings.max_consecutive_errors:
            logger.error(
                f"Max consecutive errors reached ({self._settings.max_consecutive_errors}), "
                f"backing off for {self._settings.backoff_delay}s"
            )
            time.sleep(self._settings.backoff_delay)
            self._consecutive_errors = 0
        else:
            time.sleep(self._settings.error_retry_delay)
