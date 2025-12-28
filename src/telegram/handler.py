"""Message handler for Telegram conversations."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.agent.models import AgentRunResult
from src.agent.runner import AgentRunner
from src.agent.utils.tools.registry import create_default_registry
from src.database.telegram import create_telegram_message

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.database.telegram import TelegramSession
    from src.telegram.models import TelegramMessageInfo, TelegramUpdate
    from src.telegram.utils.config import TelegramConfig
    from src.telegram.utils.session_manager import SessionManager

# Type alias for typing callback: accepts chat_id as argument
TypingCallback = Callable[[str], None]

logger = logging.getLogger(__name__)

# Template for including replied-to message context
REPLY_CONTEXT_TEMPLATE = "[Replying to previous message: {quoted_text}]\n\n{message}"

# Pattern to match Telegram commands (e.g., /newchat, /help)
# Captures: group 1 = command name, group 2 = optional args (may be None)
COMMAND_PATTERN = re.compile(r"^/([a-zA-Z_]+)(?:\s+(.*))?$", re.DOTALL)


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
    - Invoke AI Agent
    - Persist messages and tool events
    - Return plain-text response
    """

    def __init__(
        self,
        settings: TelegramConfig,
        session_manager: SessionManager,
        agent_runner: AgentRunner | None = None,
        typing_callback: TypingCallback | None = None,
    ) -> None:
        """Initialise the message handler.

        :param settings: Telegram settings.
        :param session_manager: Session manager for session lifecycle.
        :param agent_runner: Optional agent runner. If not provided, one will
            be created with the default tool registry.
        :param typing_callback: Optional callback to send typing indicator.
            Called with chat_id before agent invocation.
        """
        self._settings = settings
        self._session_manager = session_manager
        self._agent_runner = agent_runner
        self._typing_callback = typing_callback

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

    def handle_update(
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
            return self._handle_command(db_session, chat_id, message.message_id, command)

        # Handle regular message (with optional reply context)
        return self._handle_message(
            db_session,
            chat_id,
            text,
            message.message_id,
            reply_to_message=message.reply_to_message,
        )

    def _handle_command(
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
            return self._handle_message(
                db_session,
                chat_id,
                f"/{command.name}" + (f" {command.args}" if command.args else ""),
                telegram_message_id,
            )

        handler = getattr(self, handler_name)
        return handler(db_session, chat_id, telegram_message_id, command.args)

    def _is_chat_allowed(self, chat_id: str) -> bool:
        """Check if a chat ID is in the allowlist.

        :param chat_id: The chat ID to check.
        :returns: True if allowed, False otherwise.
        """
        return chat_id in self._settings.allowed_chat_ids_set

    def _cmd_newchat(
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
        telegram_session = self._session_manager.reset_session(db_session, chat_id)

        # Record the command in message history
        create_telegram_message(
            db_session,
            telegram_session,
            role="user",
            content="/newchat",
            telegram_message_id=telegram_message_id,
        )

        response = "Session reset. Starting a new conversation."

        create_telegram_message(
            db_session,
            telegram_session,
            role="assistant",
            content=response,
        )

        logger.info(f"Session reset via /newchat: chat_id={chat_id}")
        return response

    def _handle_message(
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
        # Get or create session
        telegram_session, is_new = self._session_manager.get_or_create_session(db_session, chat_id)

        if is_new:
            logger.info(f"Started new session for chat_id={chat_id}")

        # Build message with reply context if applicable
        agent_text = self._build_message_with_reply_context(text, reply_to_message)

        # Record user message (store the original text, not the augmented version)
        create_telegram_message(
            db_session,
            telegram_session,
            role="user",
            content=text,
            telegram_message_id=telegram_message_id,
        )

        # Ensure agent conversation exists (lazy creation)
        telegram_session = self._session_manager.ensure_agent_conversation(
            db_session, telegram_session
        )

        # Invoke agent with potentially augmented text
        response = self._invoke_agent(db_session, telegram_session, agent_text)

        # Record assistant response
        create_telegram_message(
            db_session,
            telegram_session,
            role="assistant",
            content=response,
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

    def _invoke_agent(
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

        # Send typing indicator before agent invocation
        if self._typing_callback:
            try:
                self._typing_callback(telegram_session.chat_id)
            except Exception:
                logger.warning(
                    f"Failed to send typing indicator: chat_id={telegram_session.chat_id}"
                )

        try:
            result: AgentRunResult = agent_runner.run(
                user_message=text,
                session=db_session,
                conversation_id=telegram_session.agent_conversation_id,
            )

            # Handle confirmation requests
            if result.stop_reason == "confirmation_required" and result.confirmation_request:
                confirmation = result.confirmation_request
                return (
                    f"I need your confirmation to proceed:\n\n"
                    f"{confirmation.action_summary}\n\n"
                    f"Reply 'yes' to confirm or 'no' to cancel."
                )

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
