"""Message handler for Telegram conversations."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.agent.models import AgentRunResult, ConfirmationRequest, PendingToolAction
from src.agent.runner import AgentRunner
from src.agent.utils.formatting import format_confirmation_message
from src.agent.utils.tools.registry import create_default_registry
from src.api.client import AsyncInternalAPIClient, InternalAPIClientError
from src.database.telegram import create_telegram_message

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.database.telegram import TelegramSession
    from src.messaging.telegram.client import TelegramClient
    from src.messaging.telegram.models import TelegramMessageInfo, TelegramUpdate
    from src.messaging.telegram.utils.config import TelegramConfig
    from src.messaging.telegram.utils.session_manager import SessionManager

# Type alias for async typing callback: accepts chat_id as argument
TypingCallback = Callable[[str], Awaitable[None]]

logger = logging.getLogger(__name__)

# Template for including replied-to message context
REPLY_CONTEXT_TEMPLATE = "[Replying to previous message: {quoted_text}]\n\n{message}"

# Pattern to match Telegram commands (e.g., /newchat, /help)
# Captures: group 1 = command name, group 2 = optional args (may be None)
COMMAND_PATTERN = re.compile(r"^/([a-zA-Z_]+)(?:\s+(.*))?$", re.DOTALL)

# Interval in seconds between typing indicator refreshes
TYPING_INDICATOR_INTERVAL = 4.0

# Mapping of entity ID fields to their API endpoints and name fields
# Format: field_name -> (endpoint_template, name_field)
ENTITY_ID_LOOKUPS: dict[str, tuple[str, str]] = {
    "task_id": ("/notion/tasks/{id}", "task_name"),
    "goal_id": ("/notion/goals/{id}", "goal_name"),
    "reading_item_id": ("/notion/reading-list/{id}", "title"),
}


@dataclass
class ParsedCommand:
    """Parsed Telegram command."""

    name: str
    args: str | None


def parse_command(text: str) -> ParsedCommand | None:
    """Parse a Telegram command from message text.

    :param text: The message text to parse.
    :returns: ParsedCommand if text starts with a command, None otherwise.
    """
    match = COMMAND_PATTERN.match(text.strip())
    if match:
        return ParsedCommand(
            name=match.group(1).lower(),
            args=match.group(2).strip() if match.group(2) else None,
        )
    return None


class UnauthorisedChatError(Exception):
    """Raised when a message is received from an unauthorised chat."""

    def __init__(self, chat_id: str) -> None:
        """Initialise the error.

        :param chat_id: The unauthorised chat ID.
        """
        self.chat_id = chat_id
        super().__init__(f"Unauthorised chat: {chat_id}")


class MessageHandler:
    """Handles incoming Telegram messages and routes them to the AI agent.

    Responsibilities:
    - Enforce chat ID allowlist
    - Session lookup/creation/expiry
    - /newchat command handling
    - Invoke AI Agent with concurrent typing indicator
    - Persist messages and tool events
    - Return plain-text response
    """

    def __init__(
        self,
        settings: TelegramConfig,
        session_manager: SessionManager,
        agent_runner: AgentRunner | None = None,
        telegram_client: TelegramClient | None = None,
    ) -> None:
        """Initialise the message handler.

        :param settings: Telegram settings.
        :param session_manager: Session manager for session lifecycle.
        :param agent_runner: Optional agent runner. If not provided, one will
            be created with the default tool registry.
        :param telegram_client: Optional Telegram client for sending typing indicators.
        """
        self._settings = settings
        self._session_manager = session_manager
        self._agent_runner = agent_runner
        self._telegram_client = telegram_client

    def _get_agent_runner(self) -> AgentRunner:
        """Get or create the agent runner.

        Lazily creates the agent runner to avoid initialisation issues.

        :returns: The agent runner instance.
        """
        if self._agent_runner is None:
            registry = create_default_registry()
            self._agent_runner = AgentRunner(registry=registry)
            logger.info("Created default AgentRunner")
        return self._agent_runner

    async def handle_update(
        self,
        db_session: Session,
        update: TelegramUpdate,
    ) -> str | None:
        """Handle a Telegram update and return the response text.

        :param db_session: Database session.
        :param update: The Telegram update to process.
        :returns: Response text to send, or None if no response needed.
        :raises UnauthorisedChatError: If the chat is not in the allowlist.
        """
        # Only handle updates with messages
        if update.message is None:
            logger.debug(f"Ignoring update without message: update_id={update.update_id}")
            return None

        message = update.message
        chat_id = str(message.chat.id)
        text = message.get_text_with_urls()

        # Ignore messages without text (e.g., photos, stickers)
        if not text:
            logger.debug(f"Ignoring message without text: chat_id={chat_id}")
            return None

        # Check chat ID allowlist
        if not self._is_chat_allowed(chat_id):
            logger.warning(f"Received message from unauthorised chat: chat_id={chat_id}")
            raise UnauthorisedChatError(chat_id)

        logger.info(f"Processing message: chat_id={chat_id}, text={text[:50]}...")

        # Check if message is a command
        command = parse_command(text)
        if command is not None:
            return await self._handle_command(db_session, chat_id, message.message_id, command)

        # Handle regular message (with optional reply context)
        return await self._handle_message(
            db_session,
            chat_id,
            text,
            message.message_id,
            reply_to_message=message.reply_to_message,
        )

    async def _handle_command(
        self,
        db_session: Session,
        chat_id: str,
        telegram_message_id: int,
        command: ParsedCommand,
    ) -> str:
        """Route a command to the appropriate handler.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :param telegram_message_id: Telegram message ID.
        :param command: Parsed command.
        :returns: Response text.
        """
        # Command dispatch table - add new commands here
        handlers: dict[str, str] = {
            "newchat": "_cmd_newchat",
            # Add future commands here, e.g.:
            # "help": "_cmd_help",
            # "status": "_cmd_status",
        }

        handler_name = handlers.get(command.name)
        if handler_name is None:
            logger.debug(f"Unknown command: /{command.name}")
            # Unknown commands are passed to the agent as regular messages
            return await self._handle_message(
                db_session,
                chat_id,
                f"/{command.name}" + (f" {command.args}" if command.args else ""),
                telegram_message_id,
            )

        handler = getattr(self, handler_name)
        return await handler(db_session, chat_id, telegram_message_id, command.args)

    def _is_chat_allowed(self, chat_id: str) -> bool:
        """Check if a chat ID is in the allowlist.

        :param chat_id: The chat ID to check.
        :returns: True if allowed, False otherwise.
        """
        return chat_id in self._settings.allowed_chat_ids_set

    async def _cmd_newchat(
        self,
        db_session: Session,
        chat_id: str,
        telegram_message_id: int,
        _args: str | None,
    ) -> str:
        """Handle the /newchat command to reset the session.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :param telegram_message_id: Telegram message ID.
        :param _args: Command arguments (unused for this command).
        :returns: Confirmation message.
        """
        # Wrap sync session manager call in thread
        telegram_session = await asyncio.to_thread(
            self._session_manager.reset_session, db_session, chat_id
        )

        # Record the command in message history
        await asyncio.to_thread(
            create_telegram_message,
            db_session,
            telegram_session,
            "user",
            "/newchat",
            telegram_message_id,
        )

        response = "Session reset. Starting a new conversation."

        await asyncio.to_thread(
            create_telegram_message,
            db_session,
            telegram_session,
            "assistant",
            response,
        )

        logger.info(f"Session reset via /newchat: chat_id={chat_id}")
        return response

    async def _handle_message(
        self,
        db_session: Session,
        chat_id: str,
        text: str,
        telegram_message_id: int,
        reply_to_message: TelegramMessageInfo | None = None,
    ) -> str:
        """Handle a regular message by invoking the AI agent.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :param text: Message text.
        :param telegram_message_id: Telegram message ID.
        :param reply_to_message: Optional message being replied to.
        :returns: Agent response text.
        """
        # Get or create session (sync operation)
        telegram_session, is_new = await asyncio.to_thread(
            self._session_manager.get_or_create_session, db_session, chat_id
        )

        if is_new:
            logger.info(f"Started new session for chat_id={chat_id}")

        # Build message with reply context if applicable
        agent_text = self._build_message_with_reply_context(text, reply_to_message)

        # Record user message (store the original text, not the augmented version)
        await asyncio.to_thread(
            create_telegram_message,
            db_session,
            telegram_session,
            "user",
            text,
            telegram_message_id,
        )

        # Ensure agent conversation exists (lazy creation)
        telegram_session = await asyncio.to_thread(
            self._session_manager.ensure_agent_conversation,
            db_session,
            telegram_session,
        )

        # Invoke agent with concurrent typing indicator
        response = await self._invoke_agent_with_typing(db_session, telegram_session, agent_text)

        # Prepend session expiry notification if applicable
        if is_new:
            response = f"Previous chat session expired, new session created.\n\n{response}"

        # Record assistant response
        await asyncio.to_thread(
            create_telegram_message,
            db_session,
            telegram_session,
            "assistant",
            response,
        )

        return response

    def _build_message_with_reply_context(
        self,
        text: str,
        reply_to_message: TelegramMessageInfo | None,
    ) -> str:
        """Build message text with reply context if applicable.

        :param text: The user's message text.
        :param reply_to_message: Optional message being replied to.
        :returns: Message text, potentially with reply context prepended.
        """
        if reply_to_message is None or not reply_to_message.text:
            return text

        logger.info(
            f"Including reply context: replying to message_id={reply_to_message.message_id}"
        )

        return REPLY_CONTEXT_TEMPLATE.format(
            quoted_text=reply_to_message.text,
            message=text,
        )

    async def _invoke_agent_with_typing(
        self,
        db_session: Session,
        telegram_session: TelegramSession,
        text: str,
    ) -> str:
        """Invoke the AI agent with concurrent typing indicator.

        Sends typing indicators every few seconds while the agent is processing
        to keep the Telegram typing indicator visible.

        :param db_session: Database session.
        :param telegram_session: The Telegram session.
        :param text: User message text.
        :returns: Agent response text.
        """
        chat_id = telegram_session.chat_id

        # Start typing indicator loop as a background task
        typing_task: asyncio.Task[None] | None = None
        if self._telegram_client is not None:
            typing_task = asyncio.create_task(self._send_typing_periodically(chat_id))

        try:
            return await self._invoke_agent(db_session, telegram_session, text)
        finally:
            # Cancel typing task when agent completes
            if typing_task is not None:
                typing_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await typing_task

    async def _send_typing_periodically(
        self,
        chat_id: str,
        interval: float = TYPING_INDICATOR_INTERVAL,
    ) -> None:
        """Send typing indicator periodically until cancelled.

        :param chat_id: The chat ID to send typing indicator to.
        :param interval: Seconds between typing indicator sends.
        """
        while True:
            try:
                if self._telegram_client is not None:
                    await self._telegram_client.send_chat_action(action="typing", chat_id=chat_id)
                    logger.debug(f"Sent typing indicator: chat_id={chat_id}")
            except Exception:
                logger.warning(f"Failed to send typing indicator: chat_id={chat_id}")
            await asyncio.sleep(interval)

    async def _invoke_agent(
        self,
        db_session: Session,
        telegram_session: TelegramSession,
        text: str,
    ) -> str:
        """Invoke the AI agent and return the response.

        :param db_session: Database session.
        :param telegram_session: The Telegram session.
        :param text: User message text.
        :returns: Agent response text.
        """
        agent_runner = self._get_agent_runner()

        try:
            # Run sync agent in thread pool to avoid blocking event loop
            result: AgentRunResult = await asyncio.to_thread(
                agent_runner.run,
                text,
                db_session,
                telegram_session.agent_conversation_id,
            )

            # Handle confirmation requests
            if result.stop_reason == "confirmation_required" and result.confirmation_request:
                return await self._format_confirmation_request(result.confirmation_request)

            return result.response or "I processed your request but have no response."

        except Exception:
            logger.exception(
                f"Agent execution failed: session_id={telegram_session.id}, "
                f"chat_id={telegram_session.chat_id}"
            )
            return (
                "I encountered an error while processing your request. "
                "Please try again or start a new chat with /newchat."
            )

    async def _format_confirmation_request(self, confirmation: ConfirmationRequest) -> str:
        """Format a confirmation request for display in Telegram.

        Handles both single and multiple tool confirmations.
        Looks up entity names for ID fields to make the message more readable.

        :param confirmation: The confirmation request from the agent.
        :returns: Formatted message for the user.
        """
        # Build list of (tool, entity_name) tuples
        tools_with_names: list[tuple[PendingToolAction, str | None]] = []

        for tool in confirmation.tools:
            entity_name = await self._lookup_entity_name_for_tool(tool)
            tools_with_names.append((tool, entity_name))

        return format_confirmation_message(tools_with_names)

    async def _lookup_entity_name_for_tool(self, tool: PendingToolAction) -> str | None:
        """Look up the entity name for a tool action.

        :param tool: The pending tool action.
        :returns: The entity name if found, None otherwise.
        """
        for key, value in tool.input_args.items():
            if key in ENTITY_ID_LOOKUPS and isinstance(value, str):
                return await self._lookup_entity_name(key, value)
        return None

    async def _lookup_entity_name(self, field_name: str, entity_id: str) -> str | None:
        """Look up an entity name by its ID.

        :param field_name: The field name (e.g., 'task_id', 'goal_id').
        :param entity_id: The entity's ID.
        :returns: The entity name, or None if lookup fails.
        """
        lookup_info = ENTITY_ID_LOOKUPS.get(field_name)
        if not lookup_info:
            return None

        endpoint_template, name_field = lookup_info
        endpoint = endpoint_template.format(id=entity_id)

        try:
            async with AsyncInternalAPIClient() as client:
                response = await client.get(endpoint)
                return response.get(name_field)
        except InternalAPIClientError as e:
            logger.warning(f"Failed to look up entity name: {field_name}={entity_id}, error={e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error looking up entity name: {e}")
            return None
