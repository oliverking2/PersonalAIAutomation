"""Tests for confidence classifier module."""

import json
import unittest
from typing import Any
from unittest.mock import MagicMock

from src.agent.enums import ConfidenceLevel
from src.agent.exceptions import BedrockClientError
from src.agent.utils.confidence_classifier import (
    ConfidenceClassificationParseError,
    _format_conversation_for_prompt,
    _parse_confidence_classification_response,
    classify_action_confidence,
    extract_conversation_for_classification,
)


class TestExtractConversationForClassification(unittest.TestCase):
    """Tests for extract_conversation_for_classification function."""

    def test_extracts_user_text_messages(self) -> None:
        """Test that user text messages are extracted."""
        messages = [
            {"role": "user", "content": [{"text": "Hello there"}]},
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["text"], "Hello there")

    def test_extracts_assistant_text_messages(self) -> None:
        """Test that assistant text messages are extracted."""
        messages = [
            {"role": "assistant", "content": [{"text": "How can I help?"}]},
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "assistant")
        self.assertEqual(result[0]["text"], "How can I help?")

    def test_filters_out_tool_use_blocks(self) -> None:
        """Test that tool use blocks are filtered out."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"text": "Let me check that"},
                    {"toolUse": {"toolUseId": "t1", "name": "get_task", "input": {}}},
                ],
            },
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Let me check that")

    def test_filters_out_tool_result_blocks(self) -> None:
        """Test that tool result blocks are filtered out."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "t1", "content": [{"text": "result"}]}},
                ],
            },
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 0)

    def test_joins_multiple_text_parts(self) -> None:
        """Test that multiple text parts in a message are joined."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"text": "First part"},
                    {"text": "Second part"},
                ],
            },
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "First part Second part")

    def test_handles_string_content(self) -> None:
        """Test that string content (not in dict) is handled."""
        messages = [
            {"role": "user", "content": ["Simple string message"]},
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Simple string message")

    def test_skips_messages_without_text(self) -> None:
        """Test that messages without any text content are skipped."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": "t1", "name": "update_task", "input": {}}},
                ],
            },
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 0)

    def test_full_conversation_extraction(self) -> None:
        """Test extraction of a full multi-turn conversation."""
        messages = [
            {"role": "user", "content": [{"text": "Tidy up the task"}]},
            {
                "role": "assistant",
                "content": [
                    {"text": "I see two issues. Which should I fix?"},
                ],
            },
            {"role": "user", "content": [{"text": "Both"}]},
            {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": "t1", "name": "update_task", "input": {}}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "t1", "content": [{"text": "success"}]}},
                ],
            },
        ]
        result = extract_conversation_for_classification(messages)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["text"], "Tidy up the task")
        self.assertEqual(result[1]["text"], "I see two issues. Which should I fix?")
        self.assertEqual(result[2]["text"], "Both")


class TestFormatConversationForPrompt(unittest.TestCase):
    """Tests for _format_conversation_for_prompt function."""

    def test_formats_single_message(self) -> None:
        """Test formatting a single message."""
        messages = [{"role": "user", "text": "Hello"}]
        result = _format_conversation_for_prompt(messages)

        self.assertEqual(result, "User: Hello")

    def test_formats_multi_turn_conversation(self) -> None:
        """Test formatting a multi-turn conversation."""
        messages = [
            {"role": "user", "text": "Tidy up the task"},
            {"role": "assistant", "text": "Which issues should I fix?"},
            {"role": "user", "text": "Both"},
        ]
        result = _format_conversation_for_prompt(messages)

        expected = "User: Tidy up the task\nAssistant: Which issues should I fix?\nUser: Both"
        self.assertEqual(result, expected)


class TestParseConfidenceClassificationResponse(unittest.TestCase):
    """Tests for _parse_confidence_classification_response function."""

    def test_parses_explicit_response(self) -> None:
        """Test parsing an EXPLICIT classification."""
        response = '{"level": "explicit", "reasoning": "User asked to tidy up"}'
        result = _parse_confidence_classification_response(response)

        self.assertEqual(result.level, ConfidenceLevel.EXPLICIT)
        self.assertEqual(result.reasoning, "User asked to tidy up")

    def test_parses_needs_confirmation_response(self) -> None:
        """Test parsing a NEEDS_CONFIRMATION classification."""
        response = '{"level": "needs_confirmation", "reasoning": "Vague request"}'
        result = _parse_confidence_classification_response(response)

        self.assertEqual(result.level, ConfidenceLevel.NEEDS_CONFIRMATION)
        self.assertEqual(result.reasoning, "Vague request")

    def test_handles_uppercase_level(self) -> None:
        """Test that uppercase level values are handled."""
        response = '{"level": "EXPLICIT", "reasoning": "Direct request"}'
        result = _parse_confidence_classification_response(response)

        self.assertEqual(result.level, ConfidenceLevel.EXPLICIT)

    def test_handles_markdown_code_block(self) -> None:
        """Test extraction of JSON from markdown code block."""
        response = '```json\n{"level": "explicit", "reasoning": "Clear request"}\n```'
        result = _parse_confidence_classification_response(response)

        self.assertEqual(result.level, ConfidenceLevel.EXPLICIT)

    def test_raises_on_invalid_json(self) -> None:
        """Test that invalid JSON raises parse error."""
        with self.assertRaises(ConfidenceClassificationParseError) as ctx:
            _parse_confidence_classification_response("not valid json")

        self.assertIn("Invalid JSON", str(ctx.exception))

    def test_raises_on_missing_level(self) -> None:
        """Test that missing level field raises parse error."""
        with self.assertRaises(ConfidenceClassificationParseError) as ctx:
            _parse_confidence_classification_response('{"reasoning": "test"}')

        self.assertIn("missing 'level'", str(ctx.exception))

    def test_raises_on_unknown_level(self) -> None:
        """Test that unknown level value raises parse error."""
        with self.assertRaises(ConfidenceClassificationParseError) as ctx:
            _parse_confidence_classification_response('{"level": "unknown", "reasoning": "test"}')

        self.assertIn("Unknown level", str(ctx.exception))

    def test_handles_missing_reasoning(self) -> None:
        """Test that missing reasoning defaults to empty string."""
        response = '{"level": "explicit"}'
        result = _parse_confidence_classification_response(response)

        self.assertEqual(result.reasoning, "")


class TestClassifyActionConfidence(unittest.TestCase):
    """Tests for classify_action_confidence function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_client = MagicMock()

    def test_returns_explicit_classification(self) -> None:
        """Test successful classification as EXPLICIT."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = json.dumps(
            {"level": "explicit", "reasoning": "User explicitly asked to update"}
        )

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": "Update the task due date to tomorrow"}]}
        ]

        result = classify_action_confidence(
            client=self.mock_client,
            messages=messages,
            proposed_action='update due date for "Test Task"',
        )

        self.assertEqual(result.level, ConfidenceLevel.EXPLICIT)
        self.mock_client.converse.assert_called_once()

    def test_returns_needs_confirmation_classification(self) -> None:
        """Test successful classification as NEEDS_CONFIRMATION."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = json.dumps(
            {"level": "needs_confirmation", "reasoning": "Vague request without specifics"}
        )

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": "Clean up my tasks"}]}
        ]

        result = classify_action_confidence(
            client=self.mock_client,
            messages=messages,
            proposed_action='update description for "Test Task"',
        )

        self.assertEqual(result.level, ConfidenceLevel.NEEDS_CONFIRMATION)

    def test_uses_haiku_model(self) -> None:
        """Test that Haiku model is used for classification."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = json.dumps(
            {"level": "explicit", "reasoning": "test"}
        )

        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": "Test"}]}]

        classify_action_confidence(
            client=self.mock_client, messages=messages, proposed_action="test action"
        )

        call_kwargs = self.mock_client.converse.call_args[1]
        self.assertEqual(call_kwargs["model_id"], "haiku")

    def test_defaults_to_needs_confirmation_on_api_error(self) -> None:
        """Test that API errors default to NEEDS_CONFIRMATION."""
        self.mock_client.converse.side_effect = BedrockClientError("API Error")

        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": "Test"}]}]

        result = classify_action_confidence(
            client=self.mock_client, messages=messages, proposed_action="test action"
        )

        self.assertEqual(result.level, ConfidenceLevel.NEEDS_CONFIRMATION)
        self.assertIn("API call failed", result.reasoning)

    def test_retries_on_parse_error(self) -> None:
        """Test that parse errors trigger retries."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        # First call returns invalid, second returns valid
        self.mock_client.parse_text_response.side_effect = [
            "invalid json",
            json.dumps({"level": "explicit", "reasoning": "test"}),
        ]

        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": "Test"}]}]

        result = classify_action_confidence(
            client=self.mock_client, messages=messages, proposed_action="test action"
        )

        self.assertEqual(result.level, ConfidenceLevel.EXPLICIT)
        self.assertEqual(self.mock_client.converse.call_count, 2)

    def test_defaults_to_needs_confirmation_after_all_retries_exhausted(self) -> None:
        """Test that exhausted retries default to NEEDS_CONFIRMATION."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = "always invalid"

        messages: list[dict[str, Any]] = [{"role": "user", "content": [{"text": "Test"}]}]

        result = classify_action_confidence(
            client=self.mock_client, messages=messages, proposed_action="test action"
        )

        self.assertEqual(result.level, ConfidenceLevel.NEEDS_CONFIRMATION)
        self.assertIn("failed after retries", result.reasoning)

    def test_filters_conversation_before_classification(self) -> None:
        """Test that conversation is filtered to remove tool blocks."""
        self.mock_client.converse.return_value = {"output": {"message": {}}}
        self.mock_client.parse_text_response.return_value = json.dumps(
            {"level": "explicit", "reasoning": "test"}
        )

        # Messages with tool blocks that should be filtered out
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": [{"text": "Update the task"}]},
            {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": "t1", "name": "get_task", "input": {}}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "t1", "content": [{"text": "result"}]}},
                ],
            },
        ]

        classify_action_confidence(
            client=self.mock_client, messages=messages, proposed_action="test action"
        )

        # Verify the prompt sent to converse only contains the user text
        self.mock_client.create_user_message.assert_called_once()
        prompt_arg = self.mock_client.create_user_message.call_args[0][0]
        # Should only have the user text, not tool use/result
        self.assertIn("Update the task", prompt_arg)
        self.assertNotIn("toolUse", prompt_arg)
        self.assertNotIn("toolResult", prompt_arg)


if __name__ == "__main__":
    unittest.main()
