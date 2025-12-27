"""Telegram session and message persistence."""

from src.database.telegram.models import (
    TelegramMessage,
    TelegramPollingCursor,
    TelegramSession,
)
from src.database.telegram.operations import (
    create_telegram_message,
    create_telegram_session,
    end_telegram_session,
    expire_inactive_sessions,
    get_active_session_for_chat,
    get_or_create_polling_cursor,
    get_telegram_session_by_id,
    update_polling_cursor,
    update_session_activity,
)

__all__ = [
    "TelegramMessage",
    "TelegramPollingCursor",
    "TelegramSession",
    "create_telegram_message",
    "create_telegram_session",
    "end_telegram_session",
    "expire_inactive_sessions",
    "get_active_session_for_chat",
    "get_or_create_polling_cursor",
    "get_telegram_session_by_id",
    "update_polling_cursor",
    "update_session_activity",
]
