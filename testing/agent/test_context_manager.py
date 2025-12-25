"""Tests for context management module."""

import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.agent.context_manager import (
    _format_messages_for_summary,
    append_messages,
    apply_sliding_window,
    build_context_messages,
    clear_pending_confirmation,
    load_conversation_state,
    save_conversation_state,
    set_pending_confirmation,
    should_summarise,
)
from src.agent.exceptions import BedrockClientError
from src.agent.models import ConversationState, PendingConfirmation


class TestLoadConversationState(unittest.TestCase):
    """Tests for load_conversation_state function."""

    def test_load_empty_conversation(self) -> None:
        """Test loading state from a new conversation."""
        conversation = MagicMock()
        conversation.id = uuid.uuid4()
        conversation.messages_json = None
        conversation.selected_tools = None
        conversation.pending_confirmation = None
        conversation.summary = None
        conversation.message_count = 0
        conversation.last_summarised_at = None

        state = load_conversation_state(conversation)

        self.assertEqual(state.conversation_id, conversation.id)
        self.assertEqual(state.messages, [])
        self.assertEqual(state.selected_tools, [])
        self.assertIsNone(state.pending_confirmation)
        self.assertIsNone(state.summary)
        self.assertEqual(state.message_count, 0)

    def test_load_conversation_with_messages(self) -> None:
        """Test loading state with existing messages."""
        conversation = MagicMock()
        conversation.id = uuid.uuid4()
        conversation.messages_json = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi!"}]},
        ]
        conversation.selected_tools = ["list_tasks", "create_task"]
        conversation.pending_confirmation = None
        conversation.summary = "Previous conversation about tasks"
        conversation.message_count = 2
        conversation.last_summarised_at = datetime.now(UTC)

        state = load_conversation_state(conversation)

        self.assertEqual(len(state.messages), 2)
        self.assertEqual(state.selected_tools, ["list_tasks", "create_task"])
        self.assertEqual(state.summary, "Previous conversation about tasks")
        self.assertEqual(state.message_count, 2)

    def test_load_conversation_with_pending_confirmation(self) -> None:
        """Test loading state with pending confirmation."""
        conversation = MagicMock()
        conversation.id = uuid.uuid4()
        conversation.messages_json = []
        conversation.selected_tools = []
        conversation.pending_confirmation = {
            "tool_use_id": "tool-123",
            "tool_name": "create_task",
            "tool_description": "Create a task",
            "input_args": {"name": "Test"},
            "action_summary": "Create a task",
            "selected_tools": ["create_task"],
        }
        conversation.summary = None
        conversation.message_count = 0
        conversation.last_summarised_at = None

        state = load_conversation_state(conversation)

        self.assertIsNotNone(state.pending_confirmation)
        self.assertEqual(state.pending_confirmation.tool_use_id, "tool-123")
        self.assertEqual(state.pending_confirmation.tool_name, "create_task")


class TestSaveConversationState(unittest.TestCase):
    """Tests for save_conversation_state function."""

    def test_save_state(self) -> None:
        """Test saving conversation state."""
        conversation = MagicMock()
        session = MagicMock()

        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user", "content": [{"text": "Hello"}]}],
            selected_tools=["list_tasks"],
            pending_confirmation=None,
            summary="Test summary",
            message_count=1,
            last_summarised_at=datetime.now(UTC),
        )

        save_conversation_state(session, conversation, state)

        self.assertEqual(conversation.messages_json, state.messages)
        self.assertEqual(conversation.selected_tools, state.selected_tools)
        self.assertIsNone(conversation.pending_confirmation)
        self.assertEqual(conversation.summary, state.summary)
        self.assertEqual(conversation.message_count, state.message_count)
        session.flush.assert_called_once()

    def test_save_state_with_pending_confirmation(self) -> None:
        """Test saving state with pending confirmation."""
        conversation = MagicMock()
        session = MagicMock()

        pending = PendingConfirmation(
            tool_use_id="tool-456",
            tool_name="delete_task",
            tool_description="Delete a task",
            input_args={"task_id": "123"},
            action_summary="Delete task 123",
            selected_tools=["delete_task"],
        )

        state = ConversationState(
            conversation_id=uuid.uuid4(),
            pending_confirmation=pending,
        )

        save_conversation_state(session, conversation, state)

        self.assertIsNotNone(conversation.pending_confirmation)
        self.assertEqual(conversation.pending_confirmation["tool_use_id"], "tool-456")


class TestAppendMessages(unittest.TestCase):
    """Tests for append_messages function."""

    def test_append_to_empty(self) -> None:
        """Test appending messages to empty state."""
        state = ConversationState(conversation_id=uuid.uuid4())

        append_messages(state, [{"role": "user", "content": [{"text": "Hello"}]}])

        self.assertEqual(len(state.messages), 1)
        self.assertEqual(state.message_count, 1)

    def test_append_multiple(self) -> None:
        """Test appending multiple messages."""
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user", "content": [{"text": "First"}]}],
            message_count=1,
        )

        append_messages(
            state,
            [
                {"role": "assistant", "content": [{"text": "Response"}]},
                {"role": "user", "content": [{"text": "Second"}]},
            ],
        )

        self.assertEqual(len(state.messages), 3)
        self.assertEqual(state.message_count, 3)


class TestShouldSummarise(unittest.TestCase):
    """Tests for should_summarise function."""

    def test_should_not_summarise_below_threshold(self) -> None:
        """Test that we don't summarise below window + batch threshold."""
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user"}] * 18,  # 15 + 3, below threshold of 5
        )

        self.assertFalse(should_summarise(state, window_size=15, batch_threshold=5))

    def test_should_not_summarise_at_threshold(self) -> None:
        """Test that we don't summarise exactly at threshold."""
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user"}] * 20,  # Exactly 15 + 5
        )

        self.assertFalse(should_summarise(state, window_size=15, batch_threshold=5))

    def test_should_summarise_above_threshold(self) -> None:
        """Test that we summarise when above window + batch threshold."""
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user"}] * 21,  # 15 + 5 + 1, above threshold
        )

        self.assertTrue(should_summarise(state, window_size=15, batch_threshold=5))


class TestApplySlidingWindow(unittest.TestCase):
    """Tests for apply_sliding_window function."""

    def test_no_summarisation_needed(self) -> None:
        """Test that no summarisation happens below threshold."""
        mock_client = MagicMock()
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user", "content": [{"text": f"Msg {i}"}]} for i in range(12)],
        )

        # 12 messages, window=10, threshold=5 -> need > 15 to trigger
        apply_sliding_window(state, mock_client, window_size=10, batch_threshold=5)

        self.assertEqual(len(state.messages), 12)
        mock_client.converse.assert_not_called()

    def test_summarisation_applies_window(self) -> None:
        """Test that sliding window trims messages and creates summary."""
        mock_client = MagicMock()
        mock_client.converse.return_value = {"output": {"message": {}}}
        mock_client.create_user_message.return_value = {"role": "user", "content": []}
        mock_client.parse_text_response.return_value = "Summary of older messages"

        state = ConversationState(
            conversation_id=uuid.uuid4(),
            # 25 messages, window=10, threshold=5 -> triggers at > 15
            messages=[{"role": "user", "content": [{"text": f"Msg {i}"}]} for i in range(25)],
        )

        apply_sliding_window(state, mock_client, window_size=10, batch_threshold=5)

        # Should keep last 10 messages, summarising the first 15
        self.assertEqual(len(state.messages), 10)
        self.assertEqual(state.summary, "Summary of older messages")
        self.assertIsNotNone(state.last_summarised_at)

    def test_summarisation_error_fallback(self) -> None:
        """Test that summarisation error preserves existing summary."""
        mock_client = MagicMock()
        mock_client.converse.side_effect = BedrockClientError("API error")
        mock_client.create_user_message.return_value = {"role": "user", "content": []}

        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user", "content": [{"text": f"Msg {i}"}]} for i in range(25)],
            summary="Existing summary",
        )

        apply_sliding_window(state, mock_client, window_size=10, batch_threshold=5)

        self.assertEqual(len(state.messages), 10)
        self.assertEqual(state.summary, "Existing summary")


class TestFormatMessagesForSummary(unittest.TestCase):
    """Tests for _format_messages_for_summary function."""

    def test_format_text_messages(self) -> None:
        """Test formatting text messages."""
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi there!"}]},
        ]

        formatted = _format_messages_for_summary(messages)

        self.assertIn("user: Hello", formatted)
        self.assertIn("assistant: Hi there!", formatted)

    def test_format_tool_use(self) -> None:
        """Test formatting tool use messages."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "name": "list_tasks",
                            "input": {"status": "pending"},
                        }
                    }
                ],
            }
        ]

        formatted = _format_messages_for_summary(messages)

        self.assertIn("list_tasks", formatted)
        self.assertIn("status", formatted)

    def test_format_tool_result(self) -> None:
        """Test formatting tool result messages."""
        messages = [
            {
                "role": "user",
                "content": [{"toolResult": {"status": "success"}}],
            }
        ]

        formatted = _format_messages_for_summary(messages)

        self.assertIn("Tool result: success", formatted)


class TestBuildContextMessages(unittest.TestCase):
    """Tests for build_context_messages function."""

    def test_build_without_summary(self) -> None:
        """Test building context without a summary."""
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[
                {"role": "user", "content": [{"text": "Hello"}]},
                {"role": "assistant", "content": [{"text": "Hi!"}]},
            ],
        )

        messages = build_context_messages(state)

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")

    def test_build_with_summary(self) -> None:
        """Test building context with a summary prepended."""
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            messages=[{"role": "user", "content": [{"text": "New question"}]}],
            summary="Previous discussion about tasks",
        )

        messages = build_context_messages(state)

        # Summary + ack + recent message
        self.assertEqual(len(messages), 3)
        self.assertIn("Previous discussion", messages[0]["content"][0]["text"])
        self.assertEqual(messages[1]["role"], "assistant")


class TestPendingConfirmation(unittest.TestCase):
    """Tests for pending confirmation helpers."""

    def test_set_pending_confirmation(self) -> None:
        """Test setting pending confirmation."""
        state = ConversationState(conversation_id=uuid.uuid4())
        pending = PendingConfirmation(
            tool_use_id="tool-123",
            tool_name="delete_task",
            tool_description="Delete a task",
            input_args={"task_id": "456"},
            action_summary="Delete task 456",
        )

        set_pending_confirmation(state, pending)

        self.assertEqual(state.pending_confirmation, pending)

    def test_clear_pending_confirmation(self) -> None:
        """Test clearing pending confirmation."""
        pending = PendingConfirmation(
            tool_use_id="tool-123",
            tool_name="delete_task",
            tool_description="Delete a task",
            input_args={"task_id": "456"},
            action_summary="Delete task 456",
        )
        state = ConversationState(
            conversation_id=uuid.uuid4(),
            pending_confirmation=pending,
        )

        clear_pending_confirmation(state)

        self.assertIsNone(state.pending_confirmation)


if __name__ == "__main__":
    unittest.main()
