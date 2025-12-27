"""Database operations for Telegram session and message management."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.database.telegram.models import (
    TelegramMessage,
    TelegramPollingCursor,
    TelegramSession,
)

logger = logging.getLogger(__name__)


def create_telegram_session(
    session: Session,
    chat_id: str,
    agent_conversation_id: uuid.UUID | None = None,
) -> TelegramSession:
    """Create a new Telegram session for a chat.

    :param session: Database session.
    :param chat_id: Telegram chat ID.
    :param agent_conversation_id: Optional linked agent conversation ID.
    :returns: The created Telegram session.
    """
    telegram_session = TelegramSession(
        chat_id=chat_id,
        agent_conversation_id=agent_conversation_id,
    )
    session.add(telegram_session)
    session.flush()
    logger.info(f"Created Telegram session: id={telegram_session.id}, chat_id={chat_id}")
    return telegram_session


def get_telegram_session_by_id(
    session: Session,
    session_id: uuid.UUID,
) -> TelegramSession | None:
    """Get a Telegram session by ID.

    :param session: Database session.
    :param session_id: The Telegram session ID.
    :returns: The session if found, None otherwise.
    """
    return session.query(TelegramSession).filter(TelegramSession.id == session_id).one_or_none()


def get_active_session_for_chat(
    session: Session,
    chat_id: str,
) -> TelegramSession | None:
    """Get the active session for a chat, if one exists.

    :param session: Database session.
    :param chat_id: Telegram chat ID.
    :returns: The active session if found, None otherwise.
    """
    return (
        session.query(TelegramSession)
        .filter(
            TelegramSession.chat_id == chat_id,
            TelegramSession.is_active.is_(True),
        )
        .one_or_none()
    )


def update_session_activity(
    session: Session,
    telegram_session: TelegramSession,
) -> TelegramSession:
    """Update the last activity timestamp for a session.

    :param session: Database session.
    :param telegram_session: The Telegram session to update.
    :returns: The updated session.
    """
    telegram_session.last_activity_at = datetime.now(UTC)
    session.flush()
    return telegram_session


def expire_inactive_sessions(
    session: Session,
    timeout_minutes: int = 10,
) -> int:
    """Mark sessions as inactive if they've exceeded the timeout.

    :param session: Database session.
    :param timeout_minutes: Minutes of inactivity before expiring.
    :returns: Number of sessions expired.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    expired_count = (
        session.query(TelegramSession)
        .filter(
            TelegramSession.is_active.is_(True),
            TelegramSession.last_activity_at < cutoff,
        )
        .update({"is_active": False})
    )
    if expired_count > 0:
        logger.info(f"Expired {expired_count} inactive Telegram sessions")
    session.flush()
    return expired_count


def end_telegram_session(
    session: Session,
    telegram_session: TelegramSession,
) -> TelegramSession:
    """Mark a Telegram session as ended.

    :param session: Database session.
    :param telegram_session: The session to end.
    :returns: The updated session.
    """
    telegram_session.is_active = False
    session.flush()
    logger.info(f"Ended Telegram session: id={telegram_session.id}")
    return telegram_session


def create_telegram_message(
    session: Session,
    telegram_session: TelegramSession,
    role: str,
    content: str,
    telegram_message_id: int | None = None,
) -> TelegramMessage:
    """Create a new Telegram message record.

    :param session: Database session.
    :param telegram_session: The parent Telegram session.
    :param role: Message role ('user' or 'assistant').
    :param content: Message content.
    :param telegram_message_id: Optional Telegram message ID.
    :returns: The created message.
    """
    message = TelegramMessage(
        session_id=telegram_session.id,
        role=role,
        content=content,
        telegram_message_id=telegram_message_id,
    )
    session.add(message)
    session.flush()
    logger.debug(f"Created Telegram message: role={role}, session_id={telegram_session.id}")
    return message


def get_or_create_polling_cursor(session: Session) -> TelegramPollingCursor:
    """Get or create the polling cursor record.

    There is only ever one cursor record (id=1).

    :param session: Database session.
    :returns: The polling cursor.
    """
    cursor = (
        session.query(TelegramPollingCursor).filter(TelegramPollingCursor.id == 1).one_or_none()
    )
    if cursor is None:
        cursor = TelegramPollingCursor(id=1, last_update_id=0)
        session.add(cursor)
        session.flush()
        logger.info("Created new polling cursor")
    return cursor


def update_polling_cursor(
    session: Session,
    last_update_id: int,
) -> TelegramPollingCursor:
    """Update the polling cursor with a new offset.

    :param session: Database session.
    :param last_update_id: The new last update ID.
    :returns: The updated cursor.
    """
    cursor = get_or_create_polling_cursor(session)
    cursor.last_update_id = last_update_id
    cursor.updated_at = datetime.now(UTC)
    session.flush()
    logger.debug(f"Updated polling cursor: last_update_id={last_update_id}")
    return cursor
