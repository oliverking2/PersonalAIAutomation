"""Telegram integration module for chat and newsletter alerts.

Run the polling bot with: python -m src.messaging.telegram
"""

from src.messaging.telegram.callbacks import (
    REMINDER_CALLBACK_PREFIX,
    CallbackResult,
    ReminderAction,
    _calculate_snooze_time,
    _get_tomorrow_morning,
    handle_reminder_callback,
    parse_reminder_callback,
    process_callback_query,
    process_callback_query_sync,
)
from src.messaging.telegram.client import TelegramClient, TelegramClientError
from src.messaging.telegram.handler import (
    MessageHandler,
    ParsedCommand,
    UnauthorisedChatError,
    parse_command,
)
from src.messaging.telegram.models import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    SendMessageResult,
    TelegramChat,
    TelegramMessageInfo,
    TelegramUpdate,
    TelegramUser,
)
from src.messaging.telegram.polling import PollingRunner
from src.messaging.telegram.utils.config import TelegramConfig, TelegramMode, get_telegram_settings
from src.messaging.telegram.utils.session_manager import SessionManager

__all__ = [
    "REMINDER_CALLBACK_PREFIX",
    "CallbackQuery",
    "CallbackResult",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "MessageHandler",
    "ParsedCommand",
    "PollingRunner",
    "ReminderAction",
    "SendMessageResult",
    "SessionManager",
    "TelegramChat",
    "TelegramClient",
    "TelegramClientError",
    "TelegramConfig",
    "TelegramMessageInfo",
    "TelegramMode",
    "TelegramUpdate",
    "TelegramUser",
    "UnauthorisedChatError",
    "_calculate_snooze_time",
    "_get_tomorrow_morning",
    "get_telegram_settings",
    "handle_reminder_callback",
    "parse_command",
    "parse_reminder_callback",
    "process_callback_query",
    "process_callback_query_sync",
]
