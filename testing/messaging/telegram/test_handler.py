"""Tests for Telegram message handler module."""

import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.models import PendingToolAction
from src.api.client import InternalAPIClientError
from src.messaging.telegram import (
    MessageHandler,
    UnauthorisedChatError,
    parse_command,
)
from src.messaging.telegram.models import TelegramChat, TelegramMessageInfo, TelegramUpdate
from src.messaging.telegram.utils.config import TelegramConfig


class TestMessageHandler(unittest.IsolatedAsyncioTestCase):
    """Tests for MessageHandler class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.settings = TelegramConfig(
            bot_token="test-token",
            allowed_chat_ids="12345,67890",
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

    async def test_handle_update_ignores_update_without_message(self) -> None:
        """Test that updates without messages are ignored."""
        update = TelegramUpdate(update_id=123, message=None)

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertIsNone(result)

    async def test_handle_update_ignores_message_without_text(self) -> None:
        """Test that messages without text are ignored."""
        update = self._create_update(123, 12345, None)

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertIsNone(result)

    async def test_handle_update_rejects_unauthorised_chat(self) -> None:
        """Test that messages from unauthorised chats raise error."""
        update = self._create_update(123, 99999, "Hello")

        with self.assertRaises(UnauthorisedChatError) as context:
            await self.handler.handle_update(self.mock_db_session, update)

        self.assertEqual(context.exception.chat_id, "99999")

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_handle_newchat_command(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test /newchat command resets session."""
        update = self._create_update(123, 12345, "/newchat")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        self.mock_session_manager.reset_session.return_value = mock_session

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("Session reset", result)
        self.mock_session_manager.reset_session.assert_called_once_with(
            self.mock_db_session, "12345"
        )
        # Should record both command and response
        self.assertEqual(mock_create_message.call_count, 2)

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_handle_newchat_command_case_insensitive(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test /newchat command is case insensitive."""
        update = self._create_update(123, 12345, "/NEWCHAT")

        mock_session = MagicMock()
        self.mock_session_manager.reset_session.return_value = mock_session

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("Session reset", result)

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_handle_regular_message(
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
        self.mock_session_manager.ensure_agent_conversation.return_value = mock_session

        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.response = "Hello! How can I help?"
        self.mock_agent_runner.run.return_value = mock_result

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertEqual(result, "Hello! How can I help?")
        self.mock_agent_runner.run.assert_called_once()
        # Ensure agent conversation is lazily created
        self.mock_session_manager.ensure_agent_conversation.assert_called_once()

    @patch("src.messaging.telegram.handler.AsyncInternalAPIClient")
    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_handle_message_with_confirmation_request(
        self,
        mock_create_message: MagicMock,
        mock_api_client_class: MagicMock,
    ) -> None:
        """Test handling of messages that trigger confirmation request."""
        # Mock the API client for entity name lookup
        mock_client = AsyncMock()
        mock_client.get.return_value = {"task_name": "Review quarterly report"}
        mock_api_client_class.return_value.__aenter__.return_value = mock_client
        mock_api_client_class.return_value.__aexit__.return_value = None

        update = self._create_update(123, 12345, "Update the task due date")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)
        self.mock_session_manager.ensure_agent_conversation.return_value = mock_session

        mock_tool = PendingToolAction(
            index=1,
            tool_use_id="tool-123",
            tool_name="update_task",
            tool_description="Update a task",
            input_args={"task_id": "abc-123", "due_date": "2025-01-15"},
            action_summary="Update task due date",
        )

        mock_confirmation = MagicMock()
        mock_confirmation.tools = [mock_tool]

        mock_result = MagicMock()
        mock_result.stop_reason = "confirmation_required"
        mock_result.confirmation_request = mock_confirmation
        self.mock_agent_runner.run.return_value = mock_result

        result = await self.handler.handle_update(self.mock_db_session, update)

        # New natural format: "I'll update the due date for "Review quarterly report" to 15th Jan 2025 - sound good?"
        self.assertIn("I'll", result)
        self.assertIn("sound good?", result)
        self.assertIn("due date", result)
        self.assertIn("Review quarterly report", result)
        self.assertIn("15th Jan 2025", result)

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_handle_message_agent_error(
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
        self.mock_session_manager.ensure_agent_conversation.return_value = mock_session

        self.mock_agent_runner.run.side_effect = RuntimeError("Agent failed")

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertIn("error", result.lower())

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_handle_message_with_reply_context(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test handling of messages that reply to a previous message."""
        # Create a message that replies to a previous message
        reply_to = TelegramMessageInfo(
            message_id=10,
            date=1234567880,
            chat=TelegramChat(id=12345, type="private"),
            text="What is the capital of France?",
        )
        update = TelegramUpdate(
            update_id=123,
            message=TelegramMessageInfo(
                message_id=11,
                date=1234567890,
                chat=TelegramChat(id=12345, type="private"),
                text="Please answer this",
                reply_to_message=reply_to,
            ),
        )

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.chat_id = "12345"
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)
        self.mock_session_manager.ensure_agent_conversation.return_value = mock_session

        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.response = "The capital of France is Paris."
        self.mock_agent_runner.run.return_value = mock_result

        result = await self.handler.handle_update(self.mock_db_session, update)

        self.assertEqual(result, "The capital of France is Paris.")

        # Check that the agent was called with the reply context included
        call_args = self.mock_agent_runner.run.call_args
        # Agent runner is called with positional args: (text, db_session, conversation_id)
        user_message = call_args.args[0]
        self.assertIn("What is the capital of France?", user_message)
        self.assertIn("Please answer this", user_message)
        self.assertIn("Replying to previous message", user_message)

    def test_is_chat_allowed_with_valid_chat(self) -> None:
        """Test _is_chat_allowed returns True for allowed chats."""
        self.assertTrue(self.handler._is_chat_allowed("12345"))
        self.assertTrue(self.handler._is_chat_allowed("67890"))

    def test_is_chat_allowed_with_invalid_chat(self) -> None:
        """Test _is_chat_allowed returns False for disallowed chats."""
        self.assertFalse(self.handler._is_chat_allowed("99999"))
        self.assertFalse(self.handler._is_chat_allowed("11111"))

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_typing_indicator_sends_with_telegram_client(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test that typing indicator is sent when telegram_client is provided."""
        mock_telegram_client = AsyncMock()
        handler = MessageHandler(
            settings=self.settings,
            session_manager=self.mock_session_manager,
            agent_runner=self.mock_agent_runner,
            telegram_client=mock_telegram_client,
        )

        update = self._create_update(123, 12345, "Hello")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.chat_id = "12345"
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)
        self.mock_session_manager.ensure_agent_conversation.return_value = mock_session

        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.response = "Response"
        self.mock_agent_runner.run.return_value = mock_result

        await handler.handle_update(self.mock_db_session, update)

        # Verify typing was sent at least once
        mock_telegram_client.send_chat_action.assert_called()

    @patch("src.messaging.telegram.handler.create_telegram_message")
    async def test_typing_error_does_not_block_agent(
        self,
        mock_create_message: MagicMock,
    ) -> None:
        """Test that typing error doesn't prevent agent invocation."""
        mock_telegram_client = AsyncMock()
        mock_telegram_client.send_chat_action.side_effect = RuntimeError("Typing failed")
        handler = MessageHandler(
            settings=self.settings,
            session_manager=self.mock_session_manager,
            agent_runner=self.mock_agent_runner,
            telegram_client=mock_telegram_client,
        )

        update = self._create_update(123, 12345, "Hello")

        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.chat_id = "12345"
        mock_session.agent_conversation_id = uuid.uuid4()
        self.mock_session_manager.get_or_create_session.return_value = (mock_session, False)
        self.mock_session_manager.ensure_agent_conversation.return_value = mock_session

        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.response = "Response"
        self.mock_agent_runner.run.return_value = mock_result

        result = await handler.handle_update(self.mock_db_session, update)

        # Agent should still be called despite typing error
        self.mock_agent_runner.run.assert_called_once()
        self.assertEqual(result, "Response")


class TestUnauthorisedChatError(unittest.TestCase):
    """Tests for UnauthorisedChatError exception."""

    def test_error_contains_chat_id(self) -> None:
        """Test that error contains the chat ID."""
        error = UnauthorisedChatError("12345")

        self.assertEqual(error.chat_id, "12345")
        self.assertIn("12345", str(error))


class TestParseCommand(unittest.TestCase):
    """Tests for parse_command function."""

    def test_parse_simple_command(self) -> None:
        """Test parsing a simple command without arguments."""
        result = parse_command("/newchat")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "newchat")
        self.assertIsNone(result.args)

    def test_parse_command_with_args(self) -> None:
        """Test parsing a command with arguments."""
        result = parse_command("/newchat test message")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "newchat")
        self.assertEqual(result.args, "test message")

    def test_parse_command_case_insensitive(self) -> None:
        """Test that command names are lowercased."""
        result = parse_command("/NEWCHAT")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "newchat")

    def test_parse_command_with_leading_whitespace(self) -> None:
        """Test parsing command with leading whitespace."""
        result = parse_command("  /help")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "help")

    def test_parse_command_with_multiline_args(self) -> None:
        """Test parsing command with multiline arguments."""
        result = parse_command("/cmd arg1\narg2\narg3")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "cmd")
        self.assertEqual(result.args, "arg1\narg2\narg3")

    def test_parse_non_command_returns_none(self) -> None:
        """Test that non-commands return None."""
        self.assertIsNone(parse_command("hello"))
        self.assertIsNone(parse_command("not a command"))
        self.assertIsNone(parse_command(""))

    def test_parse_command_with_underscore(self) -> None:
        """Test parsing command with underscore in name."""
        result = parse_command("/my_command")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "my_command")


class TestLookupEntityName(unittest.IsolatedAsyncioTestCase):
    """Tests for _lookup_entity_name method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.settings = TelegramConfig(
            bot_token="test-token",
            allowed_chat_ids="12345",
            _env_file=None,
        )
        self.mock_session_manager = MagicMock()
        self.handler = MessageHandler(
            settings=self.settings,
            session_manager=self.mock_session_manager,
        )

    @patch("src.messaging.telegram.handler.AsyncInternalAPIClient")
    async def test_lookup_task_name(self, mock_api_client_class: MagicMock) -> None:
        """Test looking up task name by ID."""
        mock_client = AsyncMock()
        mock_client.get.return_value = {"task_name": "Review quarterly report"}
        mock_api_client_class.return_value.__aenter__.return_value = mock_client
        mock_api_client_class.return_value.__aexit__.return_value = None

        result = await self.handler._lookup_entity_name("task_id", "task-123")

        self.assertEqual(result, "Review quarterly report")
        mock_client.get.assert_called_once_with("/notion/tasks/task-123")

    @patch("src.messaging.telegram.handler.AsyncInternalAPIClient")
    async def test_lookup_goal_name(self, mock_api_client_class: MagicMock) -> None:
        """Test looking up goal name by ID."""
        mock_client = AsyncMock()
        mock_client.get.return_value = {"goal_name": "Learn Spanish"}
        mock_api_client_class.return_value.__aenter__.return_value = mock_client
        mock_api_client_class.return_value.__aexit__.return_value = None

        result = await self.handler._lookup_entity_name("goal_id", "goal-456")

        self.assertEqual(result, "Learn Spanish")
        mock_client.get.assert_called_once_with("/notion/goals/goal-456")

    @patch("src.messaging.telegram.handler.AsyncInternalAPIClient")
    async def test_lookup_reading_item_title(self, mock_api_client_class: MagicMock) -> None:
        """Test looking up reading item title by ID."""
        mock_client = AsyncMock()
        mock_client.get.return_value = {"title": "Clean Code"}
        mock_api_client_class.return_value.__aenter__.return_value = mock_client
        mock_api_client_class.return_value.__aexit__.return_value = None

        result = await self.handler._lookup_entity_name("reading_item_id", "reading-789")

        self.assertEqual(result, "Clean Code")
        mock_client.get.assert_called_once_with("/notion/reading-list/reading-789")

    async def test_lookup_unknown_field_returns_none(self) -> None:
        """Test that unknown field names return None."""
        result = await self.handler._lookup_entity_name("unknown_id", "some-id")

        self.assertIsNone(result)

    @patch("src.messaging.telegram.handler.AsyncInternalAPIClient")
    async def test_lookup_api_error_returns_none(
        self,
        mock_api_client_class: MagicMock,
    ) -> None:
        """Test that API errors return None gracefully."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = InternalAPIClientError("Not found", 404)
        mock_api_client_class.return_value.__aenter__.return_value = mock_client
        mock_api_client_class.return_value.__aexit__.return_value = None

        result = await self.handler._lookup_entity_name("task_id", "task-123")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
