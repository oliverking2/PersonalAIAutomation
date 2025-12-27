"""Session management for Telegram conversations."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from src.database.agent_tracking import create_agent_conversation
from src.database.telegram import (
    TelegramSession,
    create_telegram_session,
    end_telegram_session,
    expire_inactive_sessions,
    get_active_session_for_chat,
    update_session_activity,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Telegram session lifecycle.

    Handles session creation, expiration, and linkage to agent conversations.
    Each Telegram session is linked to an AgentConversation for AI state.
    """

    def __init__(
        self,
        session_timeout_minutes: int = 10,
    ) -> None:
        """Initialise the session manager.

        :param session_timeout_minutes: Minutes of inactivity before session expires.
        """
        self._session_timeout = session_timeout_minutes

    def get_or_create_session(
        self,
        db_session: Session,
        chat_id: str,
    ) -> tuple[TelegramSession, bool]:
        """Get an existing active session or create a new one.

        If an active session exists but has expired (based on last activity),
        it will be ended and a new session created.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :returns: Tuple of (session, is_new) where is_new indicates if a new
            session was created.
        """
        # First, expire any inactive sessions
        expire_inactive_sessions(db_session, self._session_timeout)

        # Try to find an active session for this chat
        telegram_session = get_active_session_for_chat(db_session, chat_id)

        if telegram_session is not None:
            # Update activity timestamp
            update_session_activity(db_session, telegram_session)
            logger.debug(
                f"Continuing existing session: session_id={telegram_session.id}, chat_id={chat_id}"
            )
            return telegram_session, False

        # Create new session with linked agent conversation
        return self._create_new_session(db_session, chat_id), True

    def reset_session(
        self,
        db_session: Session,
        chat_id: str,
    ) -> TelegramSession:
        """Reset the session for a chat (end current and create new).

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :returns: The newly created session.
        """
        # End any existing active session
        existing_session = get_active_session_for_chat(db_session, chat_id)
        if existing_session is not None:
            end_telegram_session(db_session, existing_session)
            logger.info(f"Reset session for chat_id={chat_id}")

        return self._create_new_session(db_session, chat_id)

    def _create_new_session(
        self,
        db_session: Session,
        chat_id: str,
    ) -> TelegramSession:
        """Create a new session with a linked agent conversation.

        :param db_session: Database session.
        :param chat_id: Telegram chat ID.
        :returns: The newly created session.
        """
        # Create agent conversation with chat_id as external_id
        external_id = f"telegram:{chat_id}:{uuid.uuid4().hex[:8]}"
        agent_conversation = create_agent_conversation(db_session, external_id=external_id)

        # Create telegram session linked to agent conversation
        telegram_session = create_telegram_session(
            db_session,
            chat_id=chat_id,
            agent_conversation_id=agent_conversation.id,
        )

        logger.info(
            f"Created new session: session_id={telegram_session.id}, "
            f"chat_id={chat_id}, agent_conversation_id={agent_conversation.id}"
        )

        return telegram_session
