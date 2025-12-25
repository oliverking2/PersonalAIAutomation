"""Tests for tracking module."""

import unittest
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from src.agent.call_tracking import (
    LLMCallRecord,
    TrackingContext,
    get_tracking_context,
    set_tracking_context,
)
from src.agent.enums import CallType


class TestLLMCallRecord(unittest.TestCase):
    """Tests for LLMCallRecord dataclass."""

    def test_record_stores_all_fields(self) -> None:
        """Should store all provided fields correctly."""
        record = LLMCallRecord(
            id=uuid.uuid4(),
            model_alias="sonnet",
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            call_type=CallType.CHAT,
            request_messages=[{"role": "user", "content": "Hello"}],
            response_content={"message": {"content": [{"text": "Hi"}]}},
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=25,
            estimated_cost_usd=Decimal("0.001"),
            latency_ms=500,
            called_at=datetime.now(UTC),
        )

        self.assertEqual(record.model_alias, "sonnet")
        self.assertEqual(record.call_type, "chat")
        self.assertEqual(record.input_tokens, 100)
        self.assertEqual(record.output_tokens, 50)
        self.assertEqual(record.cache_read_tokens, 25)
        self.assertEqual(record.estimated_cost_usd, Decimal("0.001"))
        self.assertEqual(record.latency_ms, 500)


class TestTrackingContext(unittest.TestCase):
    """Tests for TrackingContext."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.run_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.context = TrackingContext(
            run_id=self.run_id,
            conversation_id=self.conversation_id,
        )

    def test_initialises_with_empty_calls(self) -> None:
        """Should initialise with empty llm_calls list."""
        self.assertEqual(self.context.llm_calls, [])

    def test_initialises_without_run_id(self) -> None:
        """Should initialise without run_id for standalone tracking."""
        context = TrackingContext()
        self.assertIsNone(context.run_id)
        self.assertIsNone(context.conversation_id)
        self.assertEqual(context.llm_calls, [])

    def test_record_call_creates_record(self) -> None:
        """Should create and store an LLMCallRecord."""
        response = {
            "usage": {
                "inputTokens": 100,
                "outputTokens": 50,
                "cacheReadInputTokenCount": 10,
            },
            "output": {"message": {"content": [{"text": "Response"}]}},
        }

        record = self.context.record_call(
            model_alias="haiku",
            model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
            call_type=CallType.SELECTOR,
            request_messages=[{"role": "user", "content": [{"text": "Test"}]}],
            response=response,
            latency_ms=250,
        )

        self.assertEqual(len(self.context.llm_calls), 1)
        self.assertEqual(record.model_alias, "haiku")
        self.assertEqual(record.call_type, "selector")
        self.assertEqual(record.input_tokens, 100)
        self.assertEqual(record.output_tokens, 50)
        self.assertEqual(record.cache_read_tokens, 10)
        self.assertEqual(record.latency_ms, 250)

    def test_record_call_calculates_cost(self) -> None:
        """Should calculate estimated cost based on model and tokens."""
        response = {
            "usage": {
                "inputTokens": 1000,
                "outputTokens": 1000,
            },
            "output": {},
        }

        record = self.context.record_call(
            model_alias="haiku",
            model_id="test-model",
            call_type=CallType.CHAT,
            request_messages=[],
            response=response,
            latency_ms=100,
        )

        # haiku: $0.001/1k input + $0.005/1k output = $0.006
        self.assertEqual(record.estimated_cost_usd, Decimal("0.006"))

    def test_record_call_handles_missing_usage(self) -> None:
        """Should default to zero tokens when usage is missing."""
        response = {"output": {}}

        record = self.context.record_call(
            model_alias="haiku",
            model_id="test-model",
            call_type=CallType.CHAT,
            request_messages=[],
            response=response,
            latency_ms=100,
        )

        self.assertEqual(record.input_tokens, 0)
        self.assertEqual(record.output_tokens, 0)
        self.assertEqual(record.cache_read_tokens, 0)

    def test_total_input_tokens(self) -> None:
        """Should sum input tokens across all calls."""
        for i in range(3):
            self.context.record_call(
                model_alias="haiku",
                model_id="test",
                call_type=CallType.CHAT,
                request_messages=[],
                response={"usage": {"inputTokens": 100 * (i + 1)}, "output": {}},
                latency_ms=100,
            )

        # 100 + 200 + 300 = 600
        self.assertEqual(self.context.total_input_tokens, 600)

    def test_total_output_tokens(self) -> None:
        """Should sum output tokens across all calls."""
        for i in range(3):
            self.context.record_call(
                model_alias="haiku",
                model_id="test",
                call_type=CallType.CHAT,
                request_messages=[],
                response={"usage": {"outputTokens": 50 * (i + 1)}, "output": {}},
                latency_ms=100,
            )

        # 50 + 100 + 150 = 300
        self.assertEqual(self.context.total_output_tokens, 300)

    def test_total_cache_read_tokens(self) -> None:
        """Should sum cache read tokens across all calls."""
        for i in range(3):
            self.context.record_call(
                model_alias="haiku",
                model_id="test",
                call_type=CallType.CHAT,
                request_messages=[],
                response={
                    "usage": {"cacheReadInputTokenCount": 10 * (i + 1)},
                    "output": {},
                },
                latency_ms=100,
            )

        # 10 + 20 + 30 = 60
        self.assertEqual(self.context.total_cache_read_tokens, 60)

    def test_total_estimated_cost(self) -> None:
        """Should sum estimated costs across all calls."""
        # Record 3 haiku calls with 1000 tokens each
        for _ in range(3):
            self.context.record_call(
                model_alias="haiku",
                model_id="test",
                call_type=CallType.CHAT,
                request_messages=[],
                response={
                    "usage": {"inputTokens": 1000, "outputTokens": 1000},
                    "output": {},
                },
                latency_ms=100,
            )

        # Each call: $0.006, total: $0.018
        self.assertEqual(self.context.total_estimated_cost, Decimal("0.018"))

    def test_empty_context_totals_are_zero(self) -> None:
        """Should return zero for all totals when no calls recorded."""
        self.assertEqual(self.context.total_input_tokens, 0)
        self.assertEqual(self.context.total_output_tokens, 0)
        self.assertEqual(self.context.total_cache_read_tokens, 0)
        self.assertEqual(self.context.total_estimated_cost, Decimal("0"))


class TestTrackingContextVar(unittest.TestCase):
    """Tests for tracking context variable functions."""

    def tearDown(self) -> None:
        """Clear tracking context after each test."""
        set_tracking_context(None)

    def test_get_tracking_context_returns_none_by_default(self) -> None:
        """Should return None when no context is set."""
        result = get_tracking_context()
        self.assertIsNone(result)

    def test_set_and_get_tracking_context(self) -> None:
        """Should store and retrieve tracking context."""
        context = TrackingContext(
            run_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
        )

        set_tracking_context(context)
        result = get_tracking_context()

        self.assertIs(result, context)

    def test_set_and_get_tracking_context_without_ids(self) -> None:
        """Should store and retrieve tracking context without run/conversation IDs."""
        context = TrackingContext()

        set_tracking_context(context)
        result = get_tracking_context()

        self.assertIs(result, context)
        self.assertIsNone(result.run_id)
        self.assertIsNone(result.conversation_id)

    def test_clear_tracking_context(self) -> None:
        """Should clear context when set to None."""
        context = TrackingContext(
            run_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
        )

        set_tracking_context(context)
        set_tracking_context(None)
        result = get_tracking_context()

        self.assertIsNone(result)

    @patch("src.agent.call_tracking._tracking_context")
    def test_context_isolation(self, mock_context_var: unittest.mock.MagicMock) -> None:
        """Should use ContextVar for thread-safe isolation."""
        context = TrackingContext(
            run_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
        )

        set_tracking_context(context)

        mock_context_var.set.assert_called_with(context)


if __name__ == "__main__":
    unittest.main()
