"""Message handler for Telegram conversations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.agent.models import AgentRunResult
from src.agent.runner import AgentRunner
from src.agent.utils.tools.registry import create_default_registry
from src.database.telegram import create_telegram_message

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.database.telegram import TelegramSession
    from src.telegram.models import TelegramUpdate
    from src.telegram.utils.config import TelegramConfig
    from src.telegram.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)

# Command prefix for Telegram commands
COMMAND_NEWCHAT = "/newchat"


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
    ) -> None:
        """Initialise the message handler.

        :param settings: Telegram settings.
        :param session_manager: Session manager for session lifecycle.
        :param agent_runner: Optional agent runner. If not provided, one will
            be created with the default tool registry.
        """
        self._settings = settings
        self._session_manager = session_manager
        self._agent_runner = agent_runner

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
        text = message.text

        # Ignore messages without text (e.g., photos, stickers)
        if not text:
            logger.debug(f"Ignoring message without text: chat_id={chat_id}")
            return None

        # Check chat ID allowlist
        if not self._is_chat_allowed(chat_id):
            logger.warning(f"Received message from unauthorised chat: chat_id={chat_id}")
            raise UnauthorisedChatError(chat_id)

        logger.info(f"Processing message: chat_id={chat_id}, text={text[:50]}...")

        # Handle commands
        if text.strip().lower() == COMMAND_NEWCHAT:
            return self._handle_newchat_command(db_session, chat_id, message.message_id)

        # Handle regular message
        return self._handle_message(db_session, chat_id, text, message.message_id)

    def _is_chat_allowed(self, chat_id: str) -> bool:
        """Check if a chat ID is in the allowlist.

        :param chat_id: The chat ID to check.
        :returns: True if allowed, False otherwise.
        """
        return chat_id in self._settings.allowed_chat_ids

    def _handle_newchat_command(
        self,
        db_session: Session,
        chat_id: str,
        telegram_message_id: int,
    ) -> str:
        """Handle the /newchat command to reset the session.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :param telegram_message_id: Telegram message ID.
        :returns: Confirmation message.
        """
        telegram_session = self._session_manager.reset_session(db_session, chat_id)

        # Record the command in message history
        create_telegram_message(
            db_session,
            telegram_session,
            role="user",
            content=COMMAND_NEWCHAT,
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
    ) -> str:
        """Handle a regular message by invoking the AI agent.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :param text: Message text.
        :param telegram_message_id: Telegram message ID.
        :returns: Agent response text.
        """
        # Get or create session
        telegram_session, is_new = self._session_manager.get_or_create_session(db_session, chat_id)

        if is_new:
            logger.info(f"Started new session for chat_id={chat_id}")

        # Record user message
        create_telegram_message(
            db_session,
            telegram_session,
            role="user",
            content=text,
            telegram_message_id=telegram_message_id,
        )

        # Invoke agent
        response = self._invoke_agent(db_session, telegram_session, text)

        # Record assistant response
        create_telegram_message(
            db_session,
            telegram_session,
            role="assistant",
            content=response,
        )

        return response

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
