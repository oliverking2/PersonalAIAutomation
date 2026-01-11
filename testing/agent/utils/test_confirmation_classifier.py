"""Tests for confirmation classifier."""

import unittest
from unittest.mock import MagicMock

from src.agent.enums import ConfirmationType, ToolDecisionType
from src.agent.exceptions import BedrockClientError
from src.agent.models import PendingConfirmation, PendingToolAction
from src.agent.utils.confirmation_classifier import (
    ClassificationParseError,
    _parse_batch_classification_response,
    classify_batch_confirmation_response,
)


class TestParseBatchClassificationResponse(unittest.TestCase):
    """Tests for _parse_batch_classification_response function."""

    def test_parse_batch_confirm(self) -> None:
        """Test parsing CONFIRM response for batch."""
        response = '{"classification": "CONFIRM"}'
        result = _parse_batch_classification_response(response, tool_count=3)
        self.assertEqual(result.classification, ConfirmationType.CONFIRM)
        self.assertEqual(result.tool_decisions, [])

    def test_parse_batch_deny(self) -> None:
        """Test parsing DENY response for batch."""
        response = '{"classification": "DENY"}'
        result = _parse_batch_classification_response(response, tool_count=2)
        self.assertEqual(result.classification, ConfirmationType.DENY)
        self.assertEqual(result.tool_decisions, [])

    def test_parse_batch_partial_confirm(self) -> None:
        """Test parsing PARTIAL_CONFIRM with tool decisions."""
        response = """{
            "classification": "PARTIAL_CONFIRM",
            "tool_decisions": [
                {"index": 1, "decision": "approve"},
                {"index": 2, "decision": "reject"},
                {"index": 3, "decision": "modify", "correction": "change priority to High"}
            ]
        }"""
        result = _parse_batch_classification_response(response, tool_count=3)
        self.assertEqual(result.classification, ConfirmationType.PARTIAL_CONFIRM)
        self.assertEqual(len(result.tool_decisions), 3)
        self.assertEqual(result.tool_decisions[0].decision, ToolDecisionType.APPROVE)
        self.assertEqual(result.tool_decisions[1].decision, ToolDecisionType.REJECT)
        self.assertEqual(result.tool_decisions[2].decision, ToolDecisionType.MODIFY)
        self.assertEqual(result.tool_decisions[2].correction, "change priority to High")

    def test_parse_batch_partial_confirm_requires_decisions(self) -> None:
        """Test that PARTIAL_CONFIRM without decisions raises error."""
        response = '{"classification": "PARTIAL_CONFIRM"}'
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_batch_classification_response(response, tool_count=2)
        self.assertIn("requires tool_decisions", str(ctx.exception))

    def test_parse_batch_modify_requires_correction(self) -> None:
        """Test that MODIFY decision requires correction text."""
        response = """{
            "classification": "PARTIAL_CONFIRM",
            "tool_decisions": [{"index": 1, "decision": "modify"}]
        }"""
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_batch_classification_response(response, tool_count=1)
        self.assertIn("requires correction text", str(ctx.exception))

    def test_parse_batch_invalid_index_raises_error(self) -> None:
        """Test that invalid tool index raises error."""
        response = """{
            "classification": "PARTIAL_CONFIRM",
            "tool_decisions": [{"index": 5, "decision": "approve"}]
        }"""
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_batch_classification_response(response, tool_count=2)
        self.assertIn("out of range", str(ctx.exception))


class TestClassifyBatchConfirmationResponse(unittest.TestCase):
    """Tests for classify_batch_confirmation_response function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.pending = PendingConfirmation(
            tools=[
                PendingToolAction(
                    index=1,
                    tool_use_id="tool-123",
                    tool_name="create_task",
                    tool_description="Create a new task",
                    input_args={"name": "Test Task"},
                    action_summary="Create a new task\nArguments: name='Test Task'",
                ),
            ],
            selected_tools=["create_task", "list_tasks"],
        )

    def test_classify_confirms(self) -> None:
        """Test classification returns CONFIRM for affirmative response."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = '{"classification": "CONFIRM"}'

        result = classify_batch_confirmation_response(
            client=self.mock_client,
            user_message="yes, go ahead",
            pending=self.pending,
        )

        self.assertEqual(result.classification, ConfirmationType.CONFIRM)
        self.mock_client.converse.assert_called_once()

    def test_classify_denies(self) -> None:
        """Test classification returns DENY for negative response."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = '{"classification": "DENY"}'

        result = classify_batch_confirmation_response(
            client=self.mock_client,
            user_message="no, cancel that",
            pending=self.pending,
        )

        self.assertEqual(result.classification, ConfirmationType.DENY)

    def test_classify_new_intent(self) -> None:
        """Test classification returns NEW_INTENT for new request."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = '{"classification": "NEW_INTENT"}'

        result = classify_batch_confirmation_response(
            client=self.mock_client,
            user_message="actually, can you list my tasks first?",
            pending=self.pending,
        )

        self.assertEqual(result.classification, ConfirmationType.NEW_INTENT)

    def test_classify_partial_confirm(self) -> None:
        """Test classification returns PARTIAL_CONFIRM with decisions."""
        # Set up pending with multiple tools
        multi_pending = PendingConfirmation(
            tools=[
                PendingToolAction(
                    index=1,
                    tool_use_id="tool-1",
                    tool_name="create_task",
                    tool_description="Create a task",
                    input_args={"name": "Task 1"},
                    action_summary="Create task 1",
                ),
                PendingToolAction(
                    index=2,
                    tool_use_id="tool-2",
                    tool_name="create_task",
                    tool_description="Create a task",
                    input_args={"name": "Task 2"},
                    action_summary="Create task 2",
                ),
            ],
            selected_tools=["create_task"],
        )

        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = """{
            "classification": "PARTIAL_CONFIRM",
            "tool_decisions": [
                {"index": 1, "decision": "approve"},
                {"index": 2, "decision": "reject"}
            ]
        }"""

        result = classify_batch_confirmation_response(
            client=self.mock_client,
            user_message="yes to 1, skip 2",
            pending=multi_pending,
        )

        self.assertEqual(result.classification, ConfirmationType.PARTIAL_CONFIRM)
        self.assertEqual(len(result.tool_decisions), 2)
        self.assertEqual(result.tool_decisions[0].decision, ToolDecisionType.APPROVE)
        self.assertEqual(result.tool_decisions[1].decision, ToolDecisionType.REJECT)

    def test_classify_raises_on_api_error(self) -> None:
        """Test that API errors raise ClassificationParseError."""
        self.mock_client.converse.side_effect = BedrockClientError("API error")
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}

        with self.assertRaises(ClassificationParseError) as ctx:
            classify_batch_confirmation_response(
                client=self.mock_client,
                user_message="yes",
                pending=self.pending,
            )

        self.assertIn("API call failed", str(ctx.exception))

    def test_classify_uses_haiku_model(self) -> None:
        """Test that classifier uses haiku model for cost efficiency."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = '{"classification": "CONFIRM"}'

        classify_batch_confirmation_response(
            client=self.mock_client,
            user_message="yes",
            pending=self.pending,
        )

        call_kwargs = self.mock_client.converse.call_args.kwargs
        self.assertEqual(call_kwargs["model_id"], "haiku")

    def test_classify_retries_on_parse_error(self) -> None:
        """Test that classification retries on parse errors."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        # First call returns invalid, second returns valid
        self.mock_client.parse_text_response.side_effect = [
            "invalid json",  # First attempt fails
            '{"classification": "CONFIRM"}',  # Second succeeds
        ]

        result = classify_batch_confirmation_response(
            client=self.mock_client,
            user_message="yes",
            pending=self.pending,
        )

        self.assertEqual(result.classification, ConfirmationType.CONFIRM)
        self.assertEqual(self.mock_client.converse.call_count, 2)

    def test_classify_raises_after_all_retries_exhausted(self) -> None:
        """Test that classification raises error after all retries fail."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        # All calls return invalid JSON
        self.mock_client.parse_text_response.return_value = "invalid json"

        with self.assertRaises(ClassificationParseError) as ctx:
            classify_batch_confirmation_response(
                client=self.mock_client,
                user_message="yes",
                pending=self.pending,
            )

        self.assertIn("Failed to classify response after 3 attempts", str(ctx.exception))
        # Should have tried 3 times (initial + 2 retries)
        self.assertEqual(self.mock_client.converse.call_count, 3)

    def test_classify_does_not_retry_on_api_error(self) -> None:
        """Test that API errors do not trigger retries."""
        self.mock_client.converse.side_effect = BedrockClientError("API error")
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}

        with self.assertRaises(ClassificationParseError):
            classify_batch_confirmation_response(
                client=self.mock_client,
                user_message="yes",
                pending=self.pending,
            )

        # Should only try once for API errors
        self.assertEqual(self.mock_client.converse.call_count, 1)


if __name__ == "__main__":
    unittest.main()
