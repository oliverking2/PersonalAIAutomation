"""Tests for Telegram polling runner module."""

import unittest
from unittest.mock import MagicMock, patch

from src.telegram.models import TelegramChat, TelegramMessageInfo, TelegramUpdate
from src.telegram.polling import PollingRunner
from src.telegram.utils.config import TelegramConfig


class TestPollingRunnerGrouping(unittest.TestCase):
    """Tests for PollingRunner message grouping."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.settings = TelegramConfig(
            bot_token="test-token",
            allowed_chat_ids="12345,67890",
            _env_file=None,
        )
        self.mock_client = MagicMock()
        self.mock_handler = MagicMock()

        with patch.object(PollingRunner, "_setup_signal_handlers"):
            self.runner = PollingRunner(
                client=self.mock_client,
                settings=self.settings,
                handler=self.mock_handler,
            )

    def _create_update(
        self,
        update_id: int,
        chat_id: int,
        text: str | None,
        message_id: int = 1,
        reply_to_message: TelegramMessageInfo | None = None,
    ) -> TelegramUpdate:
        """Create a test TelegramUpdate."""
        return TelegramUpdate(
            update_id=update_id,
            message=TelegramMessageInfo(
                message_id=message_id,
                date=1234567890,
                chat=TelegramChat(id=chat_id, type="private"),
                text=text,
                reply_to_message=reply_to_message,
            ),
        )

    def test_group_updates_by_chat_single_chat(self) -> None:
        """Test grouping updates from a single chat."""
        updates = [
            self._create_update(1, 12345, "Hello"),
            self._create_update(2, 12345, "World"),
        ]

        grouped = self.runner._group_updates_by_chat(updates)

        self.assertEqual(len(grouped), 1)
        self.assertIn("12345", grouped)
        self.assertEqual(len(grouped["12345"]), 2)

    def test_group_updates_by_chat_multiple_chats(self) -> None:
        """Test grouping updates from multiple chats."""
        updates = [
            self._create_update(1, 12345, "Hello from chat 1"),
            self._create_update(2, 67890, "Hello from chat 2"),
            self._create_update(3, 12345, "More from chat 1"),
        ]

        grouped = self.runner._group_updates_by_chat(updates)

        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped["12345"]), 2)
        self.assertEqual(len(grouped["67890"]), 1)

    def test_group_updates_filters_empty_messages(self) -> None:
        """Test that updates without text are filtered out."""
        updates = [
            self._create_update(1, 12345, "Hello"),
            self._create_update(2, 12345, None),  # No text
            self._create_update(3, 12345, "World"),
        ]

        grouped = self.runner._group_updates_by_chat(updates)

        self.assertEqual(len(grouped["12345"]), 2)

    def test_group_updates_filters_updates_without_message(self) -> None:
        """Test that updates without message are filtered out."""
        updates = [
            self._create_update(1, 12345, "Hello"),
            TelegramUpdate(update_id=2, message=None),  # No message
            self._create_update(3, 12345, "World"),
        ]

        grouped = self.runner._group_updates_by_chat(updates)

        self.assertEqual(len(grouped["12345"]), 2)

    def test_process_chat_updates_combines_messages(self) -> None:
        """Test that multiple messages are combined into one."""
        updates = [
            self._create_update(1, 12345, "Hello", message_id=100),
            self._create_update(2, 12345, "World", message_id=101),
        ]

        # Mock _process_update to capture the synthetic update
        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        self.assertEqual(len(captured_updates), 1)
        self.assertEqual(captured_updates[0].message.text, "Hello\nWorld")

    def test_process_chat_updates_uses_first_message_id(self) -> None:
        """Test that the first message_id is used for tracking."""
        updates = [
            self._create_update(1, 12345, "Hello", message_id=100),
            self._create_update(2, 12345, "World", message_id=101),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        self.assertEqual(captured_updates[0].message.message_id, 100)

    def test_process_chat_updates_uses_last_update_id(self) -> None:
        """Test that the last update_id is used for the synthetic update."""
        updates = [
            self._create_update(1, 12345, "Hello"),
            self._create_update(5, 12345, "World"),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        self.assertEqual(captured_updates[0].update_id, 5)

    def test_process_chat_updates_single_message(self) -> None:
        """Test processing a single message (no combining needed)."""
        updates = [
            self._create_update(1, 12345, "Hello"),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        self.assertEqual(captured_updates[0].message.text, "Hello")

    def test_process_chat_updates_embeds_reply_context_in_text(self) -> None:
        """Test that reply context is embedded in the combined text."""
        reply_to = TelegramMessageInfo(
            message_id=50,
            date=1234567800,
            chat=TelegramChat(id=12345, type="private"),
            text="Original message being replied to",
        )
        updates = [
            self._create_update(1, 12345, "My reply", reply_to_message=reply_to),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        # Reply context should be embedded in the text
        self.assertIn("Replying to previous message", captured_updates[0].message.text)
        self.assertIn("Original message being replied to", captured_updates[0].message.text)
        self.assertIn("My reply", captured_updates[0].message.text)

    def test_process_chat_updates_embeds_reply_context_for_second_message(self) -> None:
        """Test that reply context is embedded when second message has a reply."""
        reply_to = TelegramMessageInfo(
            message_id=50,
            date=1234567800,
            chat=TelegramChat(id=12345, type="private"),
            text="Task list to extend",
        )
        updates = [
            self._create_update(1, 12345, "Hello"),
            self._create_update(2, 12345, "Extend these", reply_to_message=reply_to),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        # Combined text should include first message and second with reply context
        combined_text = captured_updates[0].message.text
        self.assertIn("Hello", combined_text)
        self.assertIn("Replying to previous message", combined_text)
        self.assertIn("Task list to extend", combined_text)
        self.assertIn("Extend these", combined_text)

    def test_process_chat_updates_embeds_multiple_reply_contexts(self) -> None:
        """Test that multiple reply contexts are embedded when multiple messages reply."""
        reply_to_1 = TelegramMessageInfo(
            message_id=50,
            date=1234567800,
            chat=TelegramChat(id=12345, type="private"),
            text="First quoted message",
        )
        reply_to_2 = TelegramMessageInfo(
            message_id=51,
            date=1234567810,
            chat=TelegramChat(id=12345, type="private"),
            text="Second quoted message",
        )
        updates = [
            self._create_update(1, 12345, "Reply to first", reply_to_message=reply_to_1),
            self._create_update(2, 12345, "Reply to second", reply_to_message=reply_to_2),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        # Both reply contexts should be embedded
        combined_text = captured_updates[0].message.text
        self.assertIn("First quoted message", combined_text)
        self.assertIn("Reply to first", combined_text)
        self.assertIn("Second quoted message", combined_text)
        self.assertIn("Reply to second", combined_text)

    def test_process_chat_updates_no_reply_context_when_none(self) -> None:
        """Test that no reply context is added when messages have no replies."""
        updates = [
            self._create_update(1, 12345, "Hello"),
            self._create_update(2, 12345, "World"),
        ]

        captured_updates: list[TelegramUpdate] = []

        def capture_update(update: TelegramUpdate) -> None:
            captured_updates.append(update)

        with patch.object(self.runner, "_process_update", side_effect=capture_update):
            self.runner._process_chat_updates("12345", updates)

        # No reply context should be present
        self.assertEqual(captured_updates[0].message.text, "Hello\nWorld")
        self.assertNotIn("Replying to previous message", captured_updates[0].message.text)


if __name__ == "__main__":
    unittest.main()
