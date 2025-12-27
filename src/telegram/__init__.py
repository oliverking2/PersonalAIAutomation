"""Telegram integration module for chat and newsletter alerts.

Run the polling bot with: python -m src.telegram
"""

from src.telegram.client import TelegramClient, TelegramClientError
from src.telegram.handler import MessageHandler, UnauthorisedChatError
from src.telegram.models import (
    SendMessageResult,
    TelegramChat,
    TelegramMessageInfo,
    TelegramUpdate,
    TelegramUser,
)
from src.telegram.utils.config import TelegramConfig, TelegramMode, get_telegram_settings
from src.telegram.utils.session_manager import SessionManager

__all__ = [
    "MessageHandler",
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
    "get_telegram_settings",
]
