"""Telegram integration module for sending newsletter alerts."""

from src.telegram.client import TelegramClient
from src.telegram.models import SendResult
from src.telegram.service import TelegramService

__all__ = ["SendResult", "TelegramClient", "TelegramService"]
