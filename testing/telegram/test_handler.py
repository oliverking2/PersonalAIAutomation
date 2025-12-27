"""Tests for Telegram message handler module."""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from src.telegram.handler import MessageHandler, UnauthorisedChatError
from src.telegram.models import TelegramChat, TelegramMessageInfo, TelegramUpdate
from src.telegram.utils.config import TelegramConfig


class TestMessageHandler(unittest.TestCase):
    """Tests for MessageHandler class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.settings = TelegramConfig(
            bot_token="test-token",
            allowed_chat_ids_raw="12345,67890",
            _env_file=None,
        )
        self.mock_session_manager = MagicMock()
        self.mock_agent_runner = MagicMock()
        self.handler = MessageHandler(
            settings=self.settings,
            session_manager=self.mock_session_manager,
            agent_runner=self.mock_agent_runner,
        )
        self.mock_db_session = MagicMock()

    def _create_update(
        self,
        update_id: int,
        chat_id: int,
        text: str | None,
        message_id: int = 1,
    ) -> TelegramUpdate:
        """Create a test TelegramUpdate."""
        return TelegramUpdate(
            update_id=update_id,
            message=TelegramMessageInfo(
                message_id=message_id,
                date=1234567890,
                chat=TelegramChat(id=chat_id, type="private"),
                text=text,
            ),
        )

    def test_handle_update_ignores_update_without_message(self) -> None:
        """Test that updates without messages are ignored."""
        update = TelegramUpdate(update_id=123, message=None)

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertIsNone(result)

    def test_handle_update_ignores_message_without_text(self) -> None:
        """Test that messages without text are ignored."""
        update = self._create_update(123, 12345, None)

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertIsNone(result)

    def test_handle_update_rejects_unauthorised_chat(self) -> None:
        """Test that messages from unauthorised chats raise error."""
        update = self._create_update(123, 99999, "Hello")

        with self.assertRaises(UnauthorisedChatError) as context:
            self.handler.handle_update(self.mock_db_session, update)

        self.assertEqual(context.exception.chat_id, "99999")

    @patch("src.telegram.handler.create_telegram_message")
    def test_handle_newchat_command(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test /newchat command resets session."""
        update = self._create_update(123, 12345, "/newchat")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        self.mock_session_manager.reset_session.return_value = mock_session

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("Session reset", result)
        self.mock_session_manager.reset_session.assert_called_once_with(
            self.mock_db_session, "12345"
        )
        # Should record both command and response
        self.assertEqual(mock_create_message.call_count, 2)

    @patch("src.telegram.handler.create_telegram_message")
    def test_handle_newchat_command_case_insensitive(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test /newchat command is case insensitive."""
        update = self._create_update(123, 12345, "/NEWCHAT")

        mock_session = MagicMock()
        self.mock_session_manager.reset_session.return_value = mock_session

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("Session reset", result)

    @patch("src.telegram.handler.create_telegram_message")
    def test_handle_regular_message(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test handling of regular messages."""
        update = self._create_update(123, 12345, "Hello, bot!")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.chat_id = "12345"
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)

        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.response = "Hello! How can I help?"
        self.mock_agent_runner.run.return_value = mock_result

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertEqual(result, "Hello! How can I help?")
        self.mock_agent_runner.run.assert_called_once()

    @patch("src.telegram.handler.create_telegram_message")
    def test_handle_message_with_confirmation_request(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test handling of messages that trigger confirmation request."""
        update = self._create_update(123, 12345, "Create a task")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)

        mock_confirmation = MagicMock()
        mock_confirmation.action_summary = "Create task: Buy groceries"

        mock_result = MagicMock()
        mock_result.stop_reason = "confirmation_required"
        mock_result.confirmation_request = mock_confirmation
        self.mock_agent_runner.run.return_value = mock_result

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("confirmation", result.lower())
        self.assertIn("Buy groceries", result)

    @patch("src.telegram.handler.create_telegram_message")
    def test_handle_message_agent_error(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test handling when agent raises an error."""
        update = self._create_update(123, 12345, "Hello")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.chat_id = "12345"
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)

        self.mock_agent_runner.run.side_effect = RuntimeError("Agent failed")

        result = self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("error", result.lower())

    def test_is_chat_allowed_with_valid_chat(self) -> None:
        """Test _is_chat_allowed returns True for allowed chats."""
        self.assertTrue(self.handler._is_chat_allowed("12345"))
        self.assertTrue(self.handler._is_chat_allowed("67890"))

    def test_is_chat_allowed_with_invalid_chat(self) -> None:
        """Test _is_chat_allowed returns False for disallowed chats."""
        self.assertFalse(self.handler._is_chat_allowed("99999"))
        self.assertFalse(self.handler._is_chat_allowed("11111"))


class TestUnauthorisedChatError(unittest.TestCase):
    """Tests for UnauthorisedChatError exception."""

    def test_error_contains_chat_id(self) -> None:
        """Test that error contains the chat ID."""
        error = UnauthorisedChatError("12345")

        self.assertEqual(error.chat_id, "12345")
        self.assertIn("12345", str(error))


if __name__ == "__main__":
    unittest.main()
