"""Long polling runner for Telegram bot."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from src.database.connection import get_session
from src.database.telegram import get_or_create_polling_cursor, update_polling_cursor
from src.messaging.telegram.callbacks import process_callback_query
from src.messaging.telegram.client import TelegramClient, TelegramClientError
from src.messaging.telegram.handler import MessageHandler, UnauthorisedChatError
from src.messaging.telegram.models import TelegramMessageInfo, TelegramUpdate
from src.messaging.telegram.utils.config import TelegramConfig, get_telegram_settings
from src.messaging.telegram.utils.formatting import format_message
from src.messaging.telegram.utils.session_manager import SessionManager
from src.paths import PROJECT_ROOT
from src.utils.logging import configure_logging

# Template for including replied-to message context (matches handler.py format)
REPLY_CONTEXT_TEMPLATE = "[Replying to previous message: {quoted_text}]\n\n{message}"

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PollingRunner:
    """Async long polling runner for receiving Telegram updates.

    Runs a continuous async loop that:
    1. Polls Telegram for updates using long polling
    2. Delegates updates to the async MessageHandler
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
        self._client = client or TelegramClient(
            bot_token=self._settings.bot_token,
            poll_timeout=self._settings.poll_timeout,
        )
        self._session_manager = SessionManager(
            session_timeout_minutes=self._settings.session_timeout_minutes
        )
        self._handler = handler or MessageHandler(
            settings=self._settings,
            session_manager=self._session_manager,
            telegram_client=self._client,
        )
        self._running = False
        self._consecutive_errors = 0

    async def run(self) -> None:
        """Start the async polling loop.

        Runs until shutdown signal is received or stop() is called.
        """
        self._running = True
        self._setup_signal_handlers()

        logger.info(
            f"Starting Telegram polling runner: poll_timeout={self._settings.poll_timeout}s, "
            f"session_timeout={self._settings.session_timeout_minutes}min"
        )

        try:
            await self._polling_loop()
        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
        finally:
            await self._client.close()
            logger.info("Polling runner stopped")

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        logger.info("Stopping polling runner...")
        self._running = False

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown.

        Uses asyncio-compatible signal handling on Unix systems.
        Falls back to no-op on Windows.
        """
        if sys.platform == "win32":
            # Windows doesn't support add_signal_handler
            logger.warning("Signal handlers not supported on Windows, use Ctrl+C")
            return

        try:
            loop = asyncio.get_running_loop()

            def signal_handler() -> None:
                logger.info("Received shutdown signal")
                self.stop()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, signal_handler)
        except RuntimeError:
            logger.warning("Could not set up signal handlers (no running event loop)")

    async def _polling_loop(self) -> None:
        """Execute the main async polling loop."""
        # Get initial offset from database (sync operation wrapped in thread)
        offset = await asyncio.to_thread(self._get_initial_offset)

        logger.info(f"Starting polling from offset={offset}")

        while self._running:
            try:
                updates = await self._client.get_updates(offset=offset)
                self._consecutive_errors = 0  # Reset on success

                if not updates:
                    continue

                # Process callback queries first (button presses)
                callback_updates = [u for u in updates if u.callback_query is not None]
                for update in callback_updates:
                    await self._process_callback_query(update)

                # Group message updates by chat_id to process multiple messages together
                message_updates = [u for u in updates if u.message is not None]
                grouped = self._group_updates_by_chat(message_updates)

                for chat_id, chat_updates in grouped.items():
                    await self._process_chat_updates(chat_id, chat_updates)

                # Update offset to highest update_id + 1
                max_update_id = max(u.update_id for u in updates)
                offset = max_update_id + 1

                # Persist offset to database (sync operation wrapped in thread)
                await asyncio.to_thread(self._persist_offset, max_update_id)

            except TelegramClientError as e:
                await self._handle_polling_error(e)

    def _get_initial_offset(self) -> int | None:
        """Get the initial offset from the database.

        Sync method called via asyncio.to_thread().

        :returns: Initial offset or None if no cursor exists.
        """
        with get_session() as db_session:
            cursor = get_or_create_polling_cursor(db_session)
            return cursor.last_update_id + 1 if cursor.last_update_id > 0 else None

    def _persist_offset(self, max_update_id: int) -> None:
        """Persist the polling offset to the database.

        Sync method called via asyncio.to_thread().

        :param max_update_id: The maximum update ID to persist.
        """
        with get_session() as db_session:
            update_polling_cursor(db_session, max_update_id)

    def _group_updates_by_chat(
        self,
        updates: list[TelegramUpdate],
    ) -> dict[str, list[TelegramUpdate]]:
        """Group updates by chat ID.

        Updates without messages or text are filtered out.

        :param updates: List of updates from Telegram.
        :returns: Dictionary mapping chat_id to list of updates.
        """
        grouped: dict[str, list[TelegramUpdate]] = {}

        for update in updates:
            if update.message is None or not update.message.text:
                continue

            chat_id = str(update.message.chat.id)
            if chat_id not in grouped:
                grouped[chat_id] = []
            grouped[chat_id].append(update)

        return grouped

    async def _process_chat_updates(
        self,
        chat_id: str,
        updates: list[TelegramUpdate],
    ) -> None:
        """Process grouped updates for a single chat.

        Combines multiple messages into one agent invocation. Reply contexts
        are embedded into each message's text before combining.

        :param chat_id: The chat ID.
        :param updates: List of updates for this chat.
        """
        # Build message texts with reply contexts embedded
        messages: list[str] = []
        for u in updates:
            if u.message:
                text = u.message.get_text_with_urls()
                if text:
                    # Embed reply context into this message's text if present
                    text = self._build_text_with_reply_context(text, u.message)
                    messages.append(text)
        combined_text = "\n".join(messages)

        # Use the first update's message_id for tracking
        first_message_id = updates[0].message.message_id if updates[0].message else 0

        if len(messages) > 1:
            logger.info(
                f"Grouped {len(messages)} messages for chat_id={chat_id}: {combined_text[:50]}..."
            )

        # Create a synthetic update with combined text for the handler
        # Note: reply contexts are already embedded in the text, so no need to pass reply_to_message
        synthetic_update = TelegramUpdate(
            update_id=updates[-1].update_id,
            message=TelegramMessageInfo(
                message_id=first_message_id,
                date=updates[0].message.date if updates[0].message else 0,
                chat=updates[0].message.chat if updates[0].message else None,  # type: ignore[arg-type]
                text=combined_text,
            ),
        )

        await self._process_update(synthetic_update)

    def _build_text_with_reply_context(
        self,
        text: str,
        message: TelegramMessageInfo,
    ) -> str:
        """Build message text with reply context if the message is a reply.

        :param text: The message text (with URLs resolved).
        :param message: The message info containing reply_to_message.
        :returns: Text with reply context prepended if applicable.
        """
        reply_to = message.reply_to_message
        if reply_to is None or not reply_to.text:
            return text

        logger.info(
            f"Including reply context: message_id={message.message_id} "
            f"replying to message_id={reply_to.message_id}"
        )

        return REPLY_CONTEXT_TEMPLATE.format(
            quoted_text=reply_to.text,
            message=text,
        )

    async def _process_update(self, update: TelegramUpdate) -> None:
        """Process a single update.

        :param update: The Telegram update to process.
        """
        try:
            with get_session() as db_session:
                response = await self._handler.handle_update(db_session, update)

                if response:
                    # Send response back to the chat
                    chat_id = str(update.message.chat.id) if update.message else None
                    if chat_id:
                        await self._send_response(chat_id, response)

        except UnauthorisedChatError as e:
            logger.warning(f"Ignored message from unauthorised chat: {e.chat_id}")
        except Exception:
            logger.exception(f"Error processing update: update_id={update.update_id}")
            # Try to send error message to user
            if update.message:
                chat_id = str(update.message.chat.id)
                await self._send_error_response(chat_id)

    async def _process_callback_query(self, update: TelegramUpdate) -> None:
        """Process a callback query (inline keyboard button press).

        :param update: The Telegram update containing a callback query.
        """
        if not update.callback_query:
            return

        try:
            await process_callback_query(self._client, update.callback_query)
            logger.debug(f"Processed callback query: id={update.callback_query.id}")
        except Exception:
            logger.exception(f"Error processing callback query: id={update.callback_query.id}")

    async def _send_response(self, chat_id: str, text: str) -> None:
        """Send a response message to a chat.

        Converts Markdown formatting to platform-specific format before sending.

        :param chat_id: Target chat ID.
        :param text: Response text (may contain Markdown formatting).
        """
        try:
            formatted_text, parse_mode = format_message(text)
            await self._client.send_message(formatted_text, chat_id=chat_id, parse_mode=parse_mode)
            logger.debug(f"Sent response to chat_id={chat_id}")
        except TelegramClientError:
            logger.exception(f"Failed to send response to chat_id={chat_id}")

    async def _send_error_response(self, chat_id: str) -> None:
        """Send a generic error response to a chat.

        :param chat_id: Target chat ID.
        """
        try:
            await self._client.send_message(
                "Sorry, I encountered an error. Please try again.",
                chat_id=chat_id,
                parse_mode="",
            )
        except TelegramClientError:
            logger.exception(f"Failed to send error response to chat_id={chat_id}")

    async def _handle_polling_error(self, error: TelegramClientError) -> None:
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
            await asyncio.sleep(self._settings.backoff_delay)
            self._consecutive_errors = 0
        else:
            await asyncio.sleep(self._settings.error_retry_delay)


def main() -> None:
    """Entry point for running the Telegram polling bot."""
    load_dotenv(PROJECT_ROOT / ".env")
    configure_logging()
    runner = PollingRunner()
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
