"""Tests for agent tracking database operations."""

import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import NoResultFound

from src.agent.enums import CallType
from src.agent.utils.call_tracking import TrackingContext
from src.database.agent_tracking import (
    AgentConversation,
    AgentRun,
    LLMCall,
    complete_agent_run,
    create_agent_conversation,
    create_agent_run,
    create_llm_call,
    end_agent_conversation,
    get_agent_conversation_by_id,
    get_agent_run_with_calls,
)


class TestCreateAgentConversation(unittest.TestCase):
    """Tests for create_agent_conversation function."""

    def test_creates_conversation_without_external_id(self) -> None:
        """Should create a conversation without external ID."""
        session = MagicMock()
        session.flush = MagicMock()

        create_agent_conversation(session)

        session.add.assert_called_once()
        session.flush.assert_called_once()
        added = session.add.call_args[0][0]
        self.assertIsInstance(added, AgentConversation)
        self.assertIsNone(added.external_id)

    def test_creates_conversation_with_external_id(self) -> None:
        """Should create a conversation with external ID."""
        session = MagicMock()

        create_agent_conversation(session, external_id="telegram:12345")

        added = session.add.call_args[0][0]
        self.assertEqual(added.external_id, "telegram:12345")


class TestGetAgentConversationById(unittest.TestCase):
    """Tests for get_agent_conversation_by_id function."""

    def test_returns_conversation_when_found(self) -> None:
        """Should return conversation when it exists."""
        conversation_id = uuid.uuid4()
        expected = AgentConversation(id=conversation_id)

        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = expected

        result = get_agent_conversation_by_id(session, conversation_id)

        self.assertEqual(result, expected)

    def test_raises_when_not_found(self) -> None:
        """Should raise NoResultFound when conversation doesn't exist."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.side_effect = NoResultFound()

        with self.assertRaises(NoResultFound):
            get_agent_conversation_by_id(session, uuid.uuid4())


class TestEndAgentConversation(unittest.TestCase):
    """Tests for end_agent_conversation function."""

    @patch("src.database.agent_tracking.operations.get_agent_conversation_by_id")
    def test_sets_ended_at_timestamp(self, mock_get: MagicMock) -> None:
        """Should set ended_at to current time."""
        conversation = AgentConversation()
        mock_get.return_value = conversation
        session = MagicMock()

        result = end_agent_conversation(session, uuid.uuid4())

        self.assertIsNotNone(result.ended_at)
        self.assertIsInstance(result.ended_at, datetime)
        session.flush.assert_called_once()


class TestCreateAgentRun(unittest.TestCase):
    """Tests for create_agent_run function."""

    def test_creates_agent_run(self) -> None:
        """Should create an agent run with pending stop_reason."""
        session = MagicMock()
        conversation_id = uuid.uuid4()

        create_agent_run(
            session,
            conversation_id=conversation_id,
            user_message="Hello, how can you help?",
        )

        session.add.assert_called_once()
        session.flush.assert_called_once()
        added = session.add.call_args[0][0]
        self.assertIsInstance(added, AgentRun)
        self.assertEqual(added.conversation_id, conversation_id)
        self.assertEqual(added.user_message, "Hello, how can you help?")
        self.assertEqual(added.stop_reason, "pending")


class TestCompleteAgentRun(unittest.TestCase):
    """Tests for complete_agent_run function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.agent_run_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.agent_run = AgentRun(
            id=self.agent_run_id,
            conversation_id=self.conversation_id,
            user_message="Test message",
            stop_reason="pending",
        )
        self.tracking_context = TrackingContext(
            run_id=self.agent_run_id,
            conversation_id=self.conversation_id,
        )

    @patch("src.database.agent_tracking.operations._update_conversation_totals")
    def test_updates_agent_run_fields(self, mock_update: MagicMock) -> None:
        """Should update agent run with completion data."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = self.agent_run

        result = complete_agent_run(
            session,
            agent_run_id=self.agent_run_id,
            tracking_context=self.tracking_context,
            final_response="Here is my response",
            stop_reason="end_turn",
            steps_taken=3,
        )

        self.assertEqual(result.final_response, "Here is my response")
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(result.steps_taken, 3)
        self.assertIsNotNone(result.ended_at)

    @patch("src.database.agent_tracking.operations._update_conversation_totals")
    def test_creates_llm_call_records(self, mock_update: MagicMock) -> None:
        """Should create LLMCall records from tracking context."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = self.agent_run

        # Add calls to tracking context
        self.tracking_context.record_call(
            model_alias="haiku",
            model_id="test-model",
            call_type=CallType.SELECTOR,
            request_messages=[{"role": "user", "content": [{"text": "Test"}]}],
            response={
                "usage": {"inputTokens": 100, "outputTokens": 50},
                "output": {"message": {}},
            },
            latency_ms=200,
        )
        self.tracking_context.record_call(
            model_alias="sonnet",
            model_id="test-model-2",
            call_type=CallType.CHAT,
            request_messages=[{"role": "user", "content": [{"text": "Test 2"}]}],
            response={
                "usage": {"inputTokens": 200, "outputTokens": 100},
                "output": {"message": {}},
            },
            latency_ms=500,
        )

        complete_agent_run(
            session,
            agent_run_id=self.agent_run_id,
            tracking_context=self.tracking_context,
            final_response="Response",
            stop_reason="end_turn",
            steps_taken=1,
        )

        # Should call session.add for each LLM call (2 times)
        # Note: add is also called in tracking setup, so check the LLMCall instances
        llm_call_adds = [
            call for call in session.add.call_args_list if isinstance(call[0][0], LLMCall)
        ]
        self.assertEqual(len(llm_call_adds), 2)

    @patch("src.database.agent_tracking.operations._update_conversation_totals")
    def test_aggregates_token_totals(self, mock_update: MagicMock) -> None:
        """Should aggregate token totals from tracking context."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = self.agent_run

        # Add call with known token counts
        self.tracking_context.record_call(
            model_alias="haiku",
            model_id="test",
            call_type=CallType.CHAT,
            request_messages=[],
            response={
                "usage": {
                    "inputTokens": 500,
                    "outputTokens": 250,
                    "cacheReadInputTokens": 100,
                    "cacheWriteInputTokens": 50,
                },
                "output": {},
            },
            latency_ms=100,
        )

        result = complete_agent_run(
            session,
            agent_run_id=self.agent_run_id,
            tracking_context=self.tracking_context,
            final_response="Response",
            stop_reason="end_turn",
            steps_taken=1,
        )

        self.assertEqual(result.total_input_tokens, 500)
        self.assertEqual(result.total_output_tokens, 250)
        self.assertEqual(result.total_cache_read_tokens, 100)
        self.assertEqual(result.total_cache_write_tokens, 50)

    @patch("src.database.agent_tracking.operations._update_conversation_totals")
    def test_calls_update_conversation_totals(self, mock_update: MagicMock) -> None:
        """Should update conversation totals after completing run."""
        session = MagicMock()
        session.query.return_value.filter.return_value.one.return_value = self.agent_run

        complete_agent_run(
            session,
            agent_run_id=self.agent_run_id,
            tracking_context=self.tracking_context,
            final_response="Response",
            stop_reason="end_turn",
            steps_taken=1,
        )

        mock_update.assert_called_once_with(session, self.conversation_id)


class TestCreateLlmCall(unittest.TestCase):
    """Tests for create_llm_call function."""

    def test_creates_llm_call_without_agent_run(self) -> None:
        """Should create an LLM call without agent_run_id."""
        session = MagicMock()
        tracking_context = TrackingContext()

        record = tracking_context.record_call(
            model_alias="haiku",
            model_id="test-model",
            call_type=CallType.CHAT,
            request_messages=[{"role": "user", "content": [{"text": "Hello"}]}],
            response={
                "usage": {"inputTokens": 100, "outputTokens": 50},
                "output": {"message": {"content": [{"text": "Hi"}]}},
            },
            latency_ms=200,
        )

        create_llm_call(session, record)

        session.add.assert_called_once()
        session.flush.assert_called_once()
        added = session.add.call_args[0][0]
        self.assertIsInstance(added, LLMCall)
        self.assertIsNone(added.agent_run_id)
        self.assertEqual(added.model_alias, "haiku")

    def test_creates_llm_call_with_agent_run(self) -> None:
        """Should create an LLM call with agent_run_id."""
        session = MagicMock()
        agent_run_id = uuid.uuid4()
        tracking_context = TrackingContext(run_id=agent_run_id)

        record = tracking_context.record_call(
            model_alias="sonnet",
            model_id="test-model",
            call_type=CallType.SELECTOR,
            request_messages=[],
            response={
                "usage": {"inputTokens": 50, "outputTokens": 25},
                "output": {},
            },
            latency_ms=100,
        )

        create_llm_call(session, record, agent_run_id=agent_run_id)

        added = session.add.call_args[0][0]
        self.assertEqual(added.agent_run_id, agent_run_id)


class TestGetAgentRunWithCalls(unittest.TestCase):
    """Tests for get_agent_run_with_calls function."""

    def test_returns_agent_run_with_loaded_calls(self) -> None:
        """Should return agent run with llm_calls relationship loaded."""
        agent_run_id = uuid.uuid4()
        expected = AgentRun(id=agent_run_id)

        session = MagicMock()
        session.query.return_value.options.return_value.filter.return_value.one.return_value = (
            expected
        )

        result = get_agent_run_with_calls(session, agent_run_id)

        self.assertEqual(result, expected)
        session.query.return_value.options.assert_called_once()


class TestAgentConversationModel(unittest.TestCase):
    """Tests for AgentConversation ORM model."""

    def test_repr(self) -> None:
        """Should return readable string representation."""
        conversation = AgentConversation(
            id=uuid.uuid4(),
            external_id="test:123",
        )
        conversation.agent_runs = []

        result = repr(conversation)

        self.assertIn("AgentConversation", result)
        self.assertIn("test:123", result)
        self.assertIn("runs=0", result)


class TestAgentRunModel(unittest.TestCase):
    """Tests for AgentRun ORM model."""

    def test_repr(self) -> None:
        """Should return readable string representation."""
        agent_run = AgentRun(
            id=uuid.uuid4(),
            stop_reason="end_turn",
            steps_taken=5,
        )

        result = repr(agent_run)

        self.assertIn("AgentRun", result)
        self.assertIn("end_turn", result)
        self.assertIn("steps=5", result)


class TestLLMCallModel(unittest.TestCase):
    """Tests for LLMCall ORM model."""

    def test_repr(self) -> None:
        """Should return readable string representation."""
        llm_call = LLMCall(
            id=uuid.uuid4(),
            model_alias="sonnet",
            input_tokens=100,
            output_tokens=50,
        )

        result = repr(llm_call)

        self.assertIn("LLMCall", result)
        self.assertIn("sonnet", result)
        self.assertIn("100/50", result)


if __name__ == "__main__":
    unittest.main()
