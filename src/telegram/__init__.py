"""Telegram integration module for chat and newsletter alerts."""

from src.telegram.client import TelegramClient, TelegramClientError
from src.telegram.handler import MessageHandler, UnauthorisedChatError
from src.telegram.models import (
    SendMessageResult,
    SendResult,
    TelegramChat,
    TelegramMessageInfo,
    TelegramUpdate,
    TelegramUser,
)
from src.telegram.polling import PollingRunner
from src.telegram.service import TelegramService
from src.telegram.utils.config import TelegramConfig, TelegramMode, get_telegram_settings
from src.telegram.utils.session_manager import SessionManager

__all__ = [
    "MessageHandler",
    "PollingRunner",
    "SendMessageResult",
    "SendResult",
    "SessionManager",
    "TelegramChat",
    "TelegramClient",
    "TelegramClientError",
    "TelegramConfig",
    "TelegramMessageInfo",
    "TelegramMode",
    "TelegramService",
    "TelegramUpdate",
    "TelegramUser",
    "UnauthorisedChatError",
    "get_telegram_settings",
]
