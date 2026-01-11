"""Tests for Telegram configuration module."""

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from src.messaging.telegram.utils.config import TelegramConfig, TelegramMode, get_telegram_settings


class TestTelegramSettings(unittest.TestCase):
    """Tests for TelegramSettings class."""

    def test_valid_settings(self) -> None:
        """Test creating settings with valid values."""
        settings = TelegramConfig(
            bot_token="test-token",
            allowed_chat_ids="123,456",
            _env_file=None,
        )

        self.assertEqual(settings.bot_token, "test-token")
        self.assertEqual(settings.mode, TelegramMode.POLLING)
        self.assertEqual(settings.poll_timeout, 30)
        self.assertEqual(settings.session_timeout_minutes, 10)
        self.assertEqual(settings.allowed_chat_ids_set, frozenset({"123", "456"}))

    def test_custom_values(self) -> None:
        """Test settings with custom values."""
        settings = TelegramConfig(
            bot_token="test-token",
            chat_id="12345",
            mode=TelegramMode.WEBHOOK,
            poll_timeout=60,
            session_timeout_minutes=15,
            allowed_chat_ids="123,456,789",
            _env_file=None,
        )

        self.assertEqual(settings.chat_id, "12345")
        self.assertEqual(settings.mode, TelegramMode.WEBHOOK)
        self.assertEqual(settings.poll_timeout, 60)
        self.assertEqual(settings.session_timeout_minutes, 15)
        self.assertEqual(settings.allowed_chat_ids_set, frozenset({"123", "456", "789"}))

    def test_missing_bot_token_raises_error(self) -> None:
        """Test that missing bot_token raises validation error."""
        with self.assertRaises(ValidationError) as context:
            TelegramConfig(allowed_chat_ids="123", _env_file=None)

        errors = context.exception.errors()
        self.assertTrue(any(e["loc"] == ("bot_token",) for e in errors))

    def test_missing_allowed_chat_ids_raises_error(self) -> None:
        """Test that missing allowed_chat_ids raises validation error."""
        with self.assertRaises(ValidationError) as context:
            TelegramConfig(bot_token="test-token", _env_file=None)

        errors = context.exception.errors()
        self.assertTrue(any(e["loc"] == ("allowed_chat_ids",) for e in errors))

    def test_empty_allowed_chat_ids_raises_error(self) -> None:
        """Test that empty allowed_chat_ids string raises validation error."""
        with self.assertRaises(ValidationError) as context:
            TelegramConfig(bot_token="test-token", allowed_chat_ids="", _env_file=None)

        errors = context.exception.errors()
        self.assertTrue(any(e["loc"] == ("allowed_chat_ids",) for e in errors))

    def test_allowed_chat_ids_whitespace_handling(self) -> None:
        """Test that whitespace in allowed_chat_ids is handled correctly."""
        settings = TelegramConfig(
            bot_token="test-token",
            allowed_chat_ids="  123 , 456  ,  789  ",
            _env_file=None,
        )

        self.assertEqual(settings.allowed_chat_ids_set, frozenset({"123", "456", "789"}))

    def test_poll_timeout_validation(self) -> None:
        """Test poll_timeout validation constraints."""
        # Too low
        with self.assertRaises(ValidationError):
            TelegramConfig(
                bot_token="test-token",
                allowed_chat_ids="123",
                poll_timeout=0,
                _env_file=None,
            )

        # Too high
        with self.assertRaises(ValidationError):
            TelegramConfig(
                bot_token="test-token",
                allowed_chat_ids="123",
                poll_timeout=100,
                _env_file=None,
            )

    def test_session_timeout_validation(self) -> None:
        """Test session_timeout_minutes validation constraints."""
        # Too low
        with self.assertRaises(ValidationError):
            TelegramConfig(
                bot_token="test-token",
                allowed_chat_ids="123",
                session_timeout_minutes=0,
                _env_file=None,
            )

        # Too high
        with self.assertRaises(ValidationError):
            TelegramConfig(
                bot_token="test-token",
                allowed_chat_ids="123",
                session_timeout_minutes=100,
                _env_file=None,
            )


class TestGetTelegramSettings(unittest.TestCase):
    """Tests for get_telegram_settings function."""

    @patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "env-token",
            "TELEGRAM_ALLOWED_CHAT_IDS": "123,456",
        },
        clear=True,
    )
    def test_settings_from_environment(self) -> None:
        """Test settings loaded from environment variables."""
        # Clear cache to ensure fresh settings
        get_telegram_settings.cache_clear()

        settings = get_telegram_settings()

        self.assertEqual(settings.bot_token, "env-token")
        self.assertEqual(settings.allowed_chat_ids_set, frozenset({"123", "456"}))

    @patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "env-token",
            "TELEGRAM_CHAT_ID": "default-chat",
            "TELEGRAM_MODE": "webhook",
            "TELEGRAM_POLL_TIMEOUT": "45",
            "TELEGRAM_SESSION_TIMEOUT_MINUTES": "20",
            "TELEGRAM_ALLOWED_CHAT_IDS": "111,222,333",
        },
        clear=True,
    )
    def test_all_settings_from_environment(self) -> None:
        """Test all settings loaded from environment."""
        # Clear cache to ensure fresh settings
        get_telegram_settings.cache_clear()

        settings = get_telegram_settings()

        self.assertEqual(settings.bot_token, "env-token")
        self.assertEqual(settings.chat_id, "default-chat")
        self.assertEqual(settings.mode, TelegramMode.WEBHOOK)
        self.assertEqual(settings.poll_timeout, 45)
        self.assertEqual(settings.session_timeout_minutes, 20)
        self.assertEqual(settings.allowed_chat_ids_set, frozenset({"111", "222", "333"}))


class TestTelegramMode(unittest.TestCase):
    """Tests for TelegramMode enum."""

    def test_polling_mode(self) -> None:
        """Test polling mode value."""
        self.assertEqual(TelegramMode.POLLING, "polling")

    def test_webhook_mode(self) -> None:
        """Test webhook mode value."""
        self.assertEqual(TelegramMode.WEBHOOK, "webhook")

    def test_mode_from_string(self) -> None:
        """Test creating mode from string."""
        self.assertEqual(TelegramMode("polling"), TelegramMode.POLLING)
        self.assertEqual(TelegramMode("webhook"), TelegramMode.WEBHOOK)


if __name__ == "__main__":
    unittest.main()
