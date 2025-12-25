"""Tests for confirmation classifier."""

import unittest
from unittest.mock import MagicMock

from src.agent.confirmation_classifier import (
    ClassificationParseError,
    _parse_classification_response,
    classify_confirmation_response,
)
from src.agent.enums import ConfirmationType
from src.agent.exceptions import BedrockClientError
from src.agent.models import PendingConfirmation


class TestParseClassificationResponse(unittest.TestCase):
    """Tests for _parse_classification_response function."""

    def test_parse_confirm(self) -> None:
        """Test parsing CONFIRM response."""
        response = '{"classification": "CONFIRM", "reasoning": "User said yes"}'
        result = _parse_classification_response(response)
        self.assertEqual(result, ConfirmationType.CONFIRM)

    def test_parse_deny(self) -> None:
        """Test parsing DENY response."""
        response = '{"classification": "DENY", "reasoning": "User said no"}'
        result = _parse_classification_response(response)
        self.assertEqual(result, ConfirmationType.DENY)

    def test_parse_new_intent(self) -> None:
        """Test parsing NEW_INTENT response."""
        response = '{"classification": "NEW_INTENT", "reasoning": "New request"}'
        result = _parse_classification_response(response)
        self.assertEqual(result, ConfirmationType.NEW_INTENT)

    def test_parse_lowercase(self) -> None:
        """Test parsing lowercase classification."""
        response = '{"classification": "confirm", "reasoning": "User agreed"}'
        result = _parse_classification_response(response)
        self.assertEqual(result, ConfirmationType.CONFIRM)

    def test_parse_markdown_code_block_raises_error(self) -> None:
        """Test that markdown code block raises ClassificationParseError."""
        response = '```json\n{"classification": "CONFIRM", "reasoning": "Yes"}\n```'
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_classification_response(response)
        self.assertIn("markdown code block", str(ctx.exception))

    def test_parse_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises ClassificationParseError."""
        response = "not valid json"
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_classification_response(response)
        self.assertIn("Invalid JSON", str(ctx.exception))

    def test_parse_missing_classification_raises_error(self) -> None:
        """Test that missing classification field raises error."""
        response = '{"reasoning": "Some reason"}'
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_classification_response(response)
        self.assertIn("missing 'classification' field", str(ctx.exception))

    def test_parse_unknown_classification_raises_error(self) -> None:
        """Test that unknown classification value raises error."""
        response = '{"classification": "UNKNOWN", "reasoning": "Unclear"}'
        with self.assertRaises(ClassificationParseError) as ctx:
            _parse_classification_response(response)
        self.assertIn("Unknown classification value", str(ctx.exception))


class TestClassifyConfirmationResponse(unittest.TestCase):
    """Tests for classify_confirmation_response function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.pending = PendingConfirmation(
            tool_use_id="tool-123",
            tool_name="create_task",
            tool_description="Create a new task",
            input_args={"name": "Test Task"},
            action_summary="Create a new task\nArguments: name='Test Task'",
            selected_tools=["create_task", "list_tasks"],
        )

    def test_classify_confirms(self) -> None:
        """Test classification returns CONFIRM for affirmative response."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = (
            '{"classification": "CONFIRM", "reasoning": "User said yes"}'
        )

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="yes, go ahead",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.CONFIRM)
        self.mock_client.converse.assert_called_once()

    def test_classify_denies(self) -> None:
        """Test classification returns DENY for negative response."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = (
            '{"classification": "DENY", "reasoning": "User declined"}'
        )

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="no, cancel that",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.DENY)

    def test_classify_new_intent(self) -> None:
        """Test classification returns NEW_INTENT for new request."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = (
            '{"classification": "NEW_INTENT", "reasoning": "New request"}'
        )

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="actually, can you list my tasks first?",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.NEW_INTENT)

    def test_classify_error_returns_new_intent(self) -> None:
        """Test that API errors return NEW_INTENT as fallback."""
        self.mock_client.converse.side_effect = BedrockClientError("API error")
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="yes",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.NEW_INTENT)

    def test_classify_uses_haiku_model(self) -> None:
        """Test that classifier uses haiku model for cost efficiency."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        self.mock_client.parse_text_response.return_value = (
            '{"classification": "CONFIRM", "reasoning": "yes"}'
        )

        classify_confirmation_response(
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
            '{"classification": "CONFIRM", "reasoning": "yes"}',  # Second succeeds
        ]

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="yes",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.CONFIRM)
        self.assertEqual(self.mock_client.converse.call_count, 2)

    def test_classify_returns_new_intent_after_all_retries_exhausted(self) -> None:
        """Test that classification returns NEW_INTENT after all retries fail."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}
        # All calls return invalid JSON
        self.mock_client.parse_text_response.return_value = "invalid json"

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="yes",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.NEW_INTENT)
        # Should have tried 3 times (initial + 2 retries)
        self.assertEqual(self.mock_client.converse.call_count, 3)

    def test_classify_does_not_retry_on_api_error(self) -> None:
        """Test that API errors do not trigger retries."""
        self.mock_client.converse.side_effect = BedrockClientError("API error")
        self.mock_client.create_user_message.return_value = {"role": "user", "content": []}

        result = classify_confirmation_response(
            client=self.mock_client,
            user_message="yes",
            pending=self.pending,
        )

        self.assertEqual(result, ConfirmationType.NEW_INTENT)
        # Should only try once for API errors
        self.assertEqual(self.mock_client.converse.call_count, 1)


if __name__ == "__main__":
    unittest.main()
