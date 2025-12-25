"""Tests for BedrockClient."""

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from src.agent.client import BedrockClient
from src.agent.exceptions import BedrockClientError

# Test model ID used across tests
TEST_MODEL_ID = "anthropic.claude-sonnet-4-5-20250514-v1:0"


class TestBedrockClient(unittest.TestCase):
    """Tests for BedrockClient."""

    @patch("src.agent.client.boto3.client")
    def test_init_with_env_var(self, mock_boto_client: MagicMock) -> None:
        """Test client initialisation with environment variable."""
        with patch.dict("os.environ", {"BEDROCK_MODEL_ID": TEST_MODEL_ID}, clear=False):
            client = BedrockClient()

            self.assertEqual(client.model_id, TEST_MODEL_ID)
            self.assertEqual(client.region_name, "eu-west-2")
            mock_boto_client.assert_called_once_with("bedrock-runtime", region_name="eu-west-2")

    @patch("src.agent.client.boto3.client")
    def test_init_without_model_id_raises_error(self, mock_boto_client: MagicMock) -> None:
        """Test that missing model ID raises ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                BedrockClient()

            self.assertIn("BEDROCK_MODEL_ID", str(ctx.exception))

    @patch("src.agent.client.boto3.client")
    def test_init_with_custom_values(self, mock_boto_client: MagicMock) -> None:
        """Test client initialisation with custom values."""
        client = BedrockClient(
            model_id="custom-model",
            region_name="us-east-1",
        )

        self.assertEqual(client.model_id, "custom-model")
        self.assertEqual(client.region_name, "us-east-1")

    @patch("src.agent.client.boto3.client")
    def test_init_from_environment(self, mock_boto_client: MagicMock) -> None:
        """Test client reads from environment variables."""
        with patch.dict(
            "os.environ",
            {"BEDROCK_MODEL_ID": "env-model", "AWS_REGION": "ap-southeast-1"},
        ):
            client = BedrockClient()

            self.assertEqual(client.model_id, "env-model")
            self.assertEqual(client.region_name, "ap-southeast-1")

    @patch("src.agent.client.boto3.client")
    def test_converse_basic(self, mock_boto_client: MagicMock) -> None:
        """Test basic converse call."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {
            "output": {"message": {"content": [{"text": "Hello"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }

        client = BedrockClient(model_id=TEST_MODEL_ID)
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        response = client.converse(messages)

        self.assertEqual(response["stopReason"], "end_turn")
        mock_bedrock.converse.assert_called_once()

    @patch("src.agent.client.boto3.client")
    def test_converse_with_system_prompt(self, mock_boto_client: MagicMock) -> None:
        """Test converse with system prompt."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {"output": {"message": {}}}

        client = BedrockClient(model_id=TEST_MODEL_ID)
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        client.converse(messages, system_prompt="Be helpful")

        call_args = mock_bedrock.converse.call_args
        self.assertIn("system", call_args.kwargs)
        self.assertEqual(call_args.kwargs["system"][0]["text"], "Be helpful")

    @patch("src.agent.client.boto3.client")
    def test_converse_with_tool_config(self, mock_boto_client: MagicMock) -> None:
        """Test converse with tool configuration."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.return_value = {"output": {"message": {}}}

        client = BedrockClient(model_id=TEST_MODEL_ID)
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]
        tool_config: dict[str, Any] = {"tools": []}

        client.converse(messages, tool_config=tool_config)

        call_args = mock_bedrock.converse.call_args
        self.assertIn("toolConfig", call_args.kwargs)

    @patch("src.agent.client.boto3.client")
    def test_converse_handles_client_error(self, mock_boto_client: MagicMock) -> None:
        """Test that ClientError is converted to BedrockClientError."""
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        mock_bedrock.converse.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
            "Converse",
        )

        client = BedrockClient(model_id=TEST_MODEL_ID)
        messages = [{"role": "user", "content": [{"text": "Hi"}]}]

        with self.assertRaises(BedrockClientError) as ctx:
            client.converse(messages)

        self.assertIn("ValidationException", str(ctx.exception))

    @patch("src.agent.client.boto3.client")
    def test_parse_tool_use(self, mock_boto_client: MagicMock) -> None:
        """Test parsing tool use blocks from response."""
        client = BedrockClient(model_id=TEST_MODEL_ID)
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

    @patch("src.agent.client.boto3.client")
    def test_parse_tool_use_empty(self, mock_boto_client: MagicMock) -> None:
        """Test parsing response with no tool uses."""
        client = BedrockClient(model_id=TEST_MODEL_ID)
        response = {"output": {"message": {"content": [{"text": "Hello"}]}}}

        tool_uses = client.parse_tool_use(response)

        self.assertEqual(len(tool_uses), 0)

    @patch("src.agent.client.boto3.client")
    def test_parse_text_response(self, mock_boto_client: MagicMock) -> None:
        """Test parsing text from response."""
        client = BedrockClient(model_id=TEST_MODEL_ID)
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

    @patch("src.agent.client.boto3.client")
    def test_create_tool_result_message(self, mock_boto_client: MagicMock) -> None:
        """Test creating tool result message."""
        client = BedrockClient(model_id=TEST_MODEL_ID)

        message = client.create_tool_result_message(
            tool_use_id="tool-1",
            result={"data": "success"},
            is_error=False,
        )

        self.assertEqual(message["role"], "user")
        tool_result = message["content"][0]["toolResult"]
        self.assertEqual(tool_result["toolUseId"], "tool-1")
        self.assertEqual(tool_result["status"], "success")

    @patch("src.agent.client.boto3.client")
    def test_create_tool_result_message_error(self, mock_boto_client: MagicMock) -> None:
        """Test creating error tool result message."""
        client = BedrockClient(model_id=TEST_MODEL_ID)

        message = client.create_tool_result_message(
            tool_use_id="tool-1",
            result={"error": "failed"},
            is_error=True,
        )

        tool_result = message["content"][0]["toolResult"]
        self.assertEqual(tool_result["status"], "error")

    @patch("src.agent.client.boto3.client")
    def test_create_user_message(self, mock_boto_client: MagicMock) -> None:
        """Test creating user message."""
        client = BedrockClient(model_id=TEST_MODEL_ID)

        message = client.create_user_message("Hello")

        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"][0]["text"], "Hello")

    @patch("src.agent.client.boto3.client")
    def test_get_stop_reason(self, mock_boto_client: MagicMock) -> None:
        """Test extracting stop reason."""
        client = BedrockClient(model_id=TEST_MODEL_ID)

        response = {"stopReason": "end_turn"}
        self.assertEqual(client.get_stop_reason(response), "end_turn")

        response_empty: dict[str, Any] = {}
        self.assertEqual(client.get_stop_reason(response_empty), "")


if __name__ == "__main__":
    unittest.main()
