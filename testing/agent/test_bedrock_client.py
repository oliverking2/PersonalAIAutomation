"""Tests for BedrockClient."""

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.agent.bedrock_client import (
    MODEL_ALIASES,
    VALID_MODEL_OPTIONS,
    BedrockClient,
    resolve_model_id,
)
from src.agent.exceptions import BedrockClientError


class TestResolveModelId(unittest.TestCase):
    """Tests for resolve_model_id function."""

    def test_resolve_haiku(self) -> None:
        """Test resolving haiku alias."""
        result = resolve_model_id("haiku")
        self.assertEqual(result, MODEL_ALIASES["haiku"])

    def test_resolve_sonnet(self) -> None:
        """Test resolving sonnet alias."""
        result = resolve_model_id("sonnet")
        self.assertEqual(result, MODEL_ALIASES["sonnet"])

    def test_resolve_opus(self) -> None:
        """Test resolving opus alias."""
        result = resolve_model_id("opus")
        self.assertEqual(result, MODEL_ALIASES["opus"])

    def test_resolve_case_insensitive(self) -> None:
        """Test that model aliases are case insensitive."""
        self.assertEqual(resolve_model_id("HAIKU"), MODEL_ALIASES["haiku"])
        self.assertEqual(resolve_model_id("Sonnet"), MODEL_ALIASES["sonnet"])
        self.assertEqual(resolve_model_id("OPUS"), MODEL_ALIASES["opus"])

    def test_resolve_invalid_raises_error(self) -> None:
        """Test that invalid model alias raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            resolve_model_id("invalid-model")

        self.assertIn("Invalid model 'invalid-model'", str(ctx.exception))
        for option in VALID_MODEL_OPTIONS:
            self.assertIn(option, str(ctx.exception))


class TestBedrockClient(unittest.TestCase):
    """Tests for BedrockClient."""

    @patch("src.agent.bedrock_client.boto3.client")
    def test_init_default_region(self, mock_boto_client: MagicMock) -> None:
        """Test client initialisation with default region."""
        with patch.dict("os.environ", {}, clear=True):
            client = BedrockClient()

            self.assertEqual(client.region_name, "eu-west-2")
            mock_boto_client.assert_called_once_with("bedrock-runtime", region_name="eu-west-2")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_init_with_custom_region(self, mock_boto_client: MagicMock) -> None:
        """Test client initialisation with custom region."""
        client = BedrockClient(region_name="us-east-1")

        self.assertEqual(client.region_name, "us-east-1")
        mock_boto_client.assert_called_once_with("bedrock-runtime", region_name="us-east-1")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_init_from_environment(self, mock_boto_client: MagicMock) -> None:
        """Test client reads region from environment variable."""
        with patch.dict("os.environ", {"AWS_REGION": "ap-southeast-1"}):
            client = BedrockClient()

            self.assertEqual(client.region_name, "ap-southeast-1")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_basic(self, mock_boto_client: MagicMock) -> None:
        """Test basic converse call."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {
            "output": {"message": {"content": [{"text": "Hello"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }

        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        response = client.converse(messages, model_id="sonnet")

        self.assertEqual(response["stopReason"], "end_turn")
        mock_bedrock.converse.assert_called_once()
        call_kwargs = mock_bedrock.converse.call_args.kwargs
        self.assertEqual(call_kwargs["modelId"], MODEL_ALIASES["sonnet"])

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_with_system_prompt(self, mock_boto_client: MagicMock) -> None:
        """Test converse with system prompt."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {"output": {"message": {}}}

        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        client.converse(messages, model_id="haiku", system_prompt="Be helpful")

        call_args = mock_bedrock.converse.call_args
        self.assertIn("system", call_args.kwargs)
        self.assertEqual(call_args.kwargs["system"][0]["text"], "Be helpful")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_with_cache_system_prompt(self, mock_boto_client: MagicMock) -> None:
        """Test converse with prompt caching enabled."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {
            "output": {"message": {}},
            "usage": {"cacheReadInputTokens": 100, "cacheWriteInputTokens": 0},
        }

        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        client.converse(
            messages, model_id="haiku", system_prompt="Be helpful", cache_system_prompt=True
        )

        call_args = mock_bedrock.converse.call_args
        system_blocks = call_args.kwargs["system"]
        self.assertEqual(len(system_blocks), 2)
        self.assertEqual(system_blocks[0]["text"], "Be helpful")
        self.assertEqual(system_blocks[1], {"cachePoint": {"type": "default"}})

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_without_cache_system_prompt(self, mock_boto_client: MagicMock) -> None:
        """Test converse without prompt caching (default)."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {"output": {"message": {}}}

        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        client.converse(
            messages, model_id="haiku", system_prompt="Be helpful", cache_system_prompt=False
        )

        call_args = mock_bedrock.converse.call_args
        system_blocks = call_args.kwargs["system"]
        self.assertEqual(len(system_blocks), 1)
        self.assertEqual(system_blocks[0], {"text": "Be helpful"})

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_with_tool_config(self, mock_boto_client: MagicMock) -> None:
        """Test converse with tool configuration."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {"output": {"message": {}}}

        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]
        tool_config: dict[str, Any] = {"tools": []}

        client.converse(messages, model_id="opus", tool_config=tool_config)

        call_args = mock_bedrock.converse.call_args
        self.assertIn("toolConfig", call_args.kwargs)

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_handles_client_error(self, mock_boto_client: MagicMock) -> None:
        """Test that ClientError is converted to BedrockClientError."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
            "Converse",
        )

        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        with self.assertRaises(BedrockClientError) as ctx:
            client.converse(messages, model_id="sonnet")

        self.assertIn("ValidationException", str(ctx.exception))

    @patch("src.agent.bedrock_client.boto3.client")
    def test_converse_invalid_model_raises_error(self, mock_boto_client: MagicMock) -> None:
        """Test that invalid model alias raises ValueError."""
        client = BedrockClient()
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        with self.assertRaises(ValueError) as ctx:
            client.converse(messages, model_id="invalid")

        self.assertIn("Invalid model 'invalid'", str(ctx.exception))

    @patch("src.agent.bedrock_client.boto3.client")
    def test_parse_tool_use(self, mock_boto_client: MagicMock) -> None:
        """Test parsing tool use blocks from response."""
        client = BedrockClient()
        response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-1",
                                "name": "search",
                                "input": {"query": "test"},
                            }
                        },
                        {"text": "I'll search for that"},
                    ]
                }
            }
        }

        tool_uses = client.parse_tool_use(response)

        self.assertEqual(len(tool_uses), 1)
        self.assertEqual(tool_uses[0]["toolUseId"], "tool-1")
        self.assertEqual(tool_uses[0]["name"], "search")
        self.assertEqual(tool_uses[0]["input"], {"query": "test"})

    @patch("src.agent.bedrock_client.boto3.client")
    def test_parse_tool_use_empty(self, mock_boto_client: MagicMock) -> None:
        """Test parsing response with no tool uses."""
        client = BedrockClient()
        response = {"output": {"message": {"content": [{"text": "Hello"}]}}}

        tool_uses = client.parse_tool_use(response)

        self.assertEqual(len(tool_uses), 0)

    @patch("src.agent.bedrock_client.boto3.client")
    def test_parse_text_response(self, mock_boto_client: MagicMock) -> None:
        """Test parsing text from response."""
        client = BedrockClient()
        response = {
            "output": {
                "message": {
                    "content": [
                        {"text": "Hello"},
                        {"text": "World"},
                    ]
                }
            }
        }

        text = client.parse_text_response(response)

        self.assertEqual(text, "Hello\nWorld")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_create_tool_result_message(self, mock_boto_client: MagicMock) -> None:
        """Test creating tool result message."""
        client = BedrockClient()

        message = client.create_tool_result_message(
            tool_use_id="tool-1",
            result={"data": "success"},
            is_error=False,
        )

        self.assertEqual(message["role"], "user")
        tool_result = message["content"][0]["toolResult"]
        self.assertEqual(tool_result["toolUseId"], "tool-1")
        self.assertEqual(tool_result["status"], "success")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_create_tool_result_message_error(self, mock_boto_client: MagicMock) -> None:
        """Test creating error tool result message."""
        client = BedrockClient()

        message = client.create_tool_result_message(
            tool_use_id="tool-1",
            result={"error": "failed"},
            is_error=True,
        )

        tool_result = message["content"][0]["toolResult"]
        self.assertEqual(tool_result["status"], "error")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_create_user_message(self, mock_boto_client: MagicMock) -> None:
        """Test creating user message."""
        client = BedrockClient()

        message = client.create_user_message("Hello")

        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"][0]["text"], "Hello")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_get_stop_reason(self, mock_boto_client: MagicMock) -> None:
        """Test extracting stop reason."""
        client = BedrockClient()

        response = {"stopReason": "end_turn"}
        self.assertEqual(client.get_stop_reason(response), "end_turn")

        response_empty: dict[str, Any] = {}
        self.assertEqual(client.get_stop_reason(response_empty), "")

    @patch("src.agent.bedrock_client.boto3.client")
    def test_create_assistant_tool_use_message(self, mock_boto_client: MagicMock) -> None:
        """Test creating assistant tool use message."""
        client = BedrockClient()

        message = client.create_assistant_tool_use_message(
            tool_use_id="tool-123",
            name="create_task",
            input_args={"name": "Test Task"},
        )

        self.assertEqual(message["role"], "assistant")
        self.assertEqual(len(message["content"]), 1)
        tool_use = message["content"][0]["toolUse"]
        self.assertEqual(tool_use["toolUseId"], "tool-123")
        self.assertEqual(tool_use["name"], "create_task")
        self.assertEqual(tool_use["input"], {"name": "Test Task"})


class TestExtractJsonFromMarkdown(unittest.TestCase):
    """Tests for extract_json_from_markdown static method."""

    def test_extract_plain_json(self) -> None:
        """Test that plain JSON is returned unchanged."""
        text = '{"key": "value"}'
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_extract_plain_json_with_whitespace(self) -> None:
        """Test that plain JSON with leading/trailing whitespace is trimmed."""
        text = '  {"key": "value"}  \n'
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_extract_from_json_code_block(self) -> None:
        """Test extracting JSON from ```json code block."""
        text = '```json\n{"key": "value"}\n```'
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_extract_from_plain_code_block(self) -> None:
        """Test extracting JSON from plain ``` code block."""
        text = '```\n{"key": "value"}\n```'
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, '{"key": "value"}')

    def test_extract_multiline_json(self) -> None:
        """Test extracting multiline JSON from code block."""
        text = '```json\n{\n  "tool_names": ["query_tasks"],\n  "reasoning": "test"\n}\n```'
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertIn('"tool_names"', result)
        self.assertIn('"reasoning"', result)

    def test_extract_empty_code_block_returns_original(self) -> None:
        """Test that empty code block returns original text."""
        text = "```\n```"
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, text)

    def test_extract_code_block_with_only_markers(self) -> None:
        """Test code block with no content between markers returns original."""
        text = "```json\n```"
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, text)

    def test_extract_preserves_inner_backticks(self) -> None:
        """Test that inner content with backticks is preserved."""
        text = '```json\n{"code": "use `func()`"}\n```'
        result = BedrockClient.extract_json_from_markdown(text)
        self.assertEqual(result, '{"code": "use `func()`"}')


if __name__ == "__main__":
    unittest.main()
