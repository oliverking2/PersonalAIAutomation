"""AWS Bedrock client for the AI agent module."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from src.agent.call_tracking import get_tracking_context
from src.agent.enums import CallType
from src.agent.exceptions import BedrockClientError

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
    from mypy_boto3_bedrock_runtime.type_defs import (
        ContentBlockTypeDef,
        MessageTypeDef,
        ToolConfigurationTypeDef,
    )

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60

# Model ID aliases - use these instead of full Bedrock model IDs
MODEL_ALIASES: dict[str, str] = {
    "haiku": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "sonnet": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "opus": "global.anthropic.claude-opus-4-5-20251101-v1:0",
}

# Valid model alias options
VALID_MODEL_OPTIONS = frozenset(MODEL_ALIASES.keys())


def resolve_model_id(model_id: str) -> str:
    """Resolve a model alias to a full model ID.

    :param model_id: Model alias (haiku, sonnet, opus).
    :returns: Full Bedrock model ID.
    :raises ValueError: If model_id is not a valid alias.
    """
    model_lower = model_id.lower()
    if model_lower not in MODEL_ALIASES:
        valid_options = ", ".join(sorted(VALID_MODEL_OPTIONS))
        raise ValueError(f"Invalid model '{model_id}'. Must be one of: {valid_options}")
    return MODEL_ALIASES[model_lower]


class BedrockClient:
    """Client for AWS Bedrock Converse API.

    Provides a typed interface for invoking Claude models with tool use
    via the Bedrock Converse API. This is a low-level client that does not
    manage model selection - callers must specify the model for each request.
    """

    def __init__(
        self,
        region_name: str | None = None,
    ) -> None:
        """Initialise the Bedrock client.

        :param region_name: AWS region. Defaults to AWS_REGION env var or eu-west-2.
        """
        self.region_name = region_name or os.environ.get("AWS_REGION", "eu-west-2")

        self._client: BedrockRuntimeClient = boto3.client(
            "bedrock-runtime",
            region_name=self.region_name,
        )

        logger.debug(f"Initialised BedrockClient: region={self.region_name}")

    def converse(  # noqa: PLR0913 - Bedrock API has multiple config options
        self,
        messages: list[MessageTypeDef],
        model_id: str,
        system_prompt: str | None = None,
        tool_config: ToolConfigurationTypeDef | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        call_type: CallType = CallType.CHAT,
        cache_system_prompt: bool = True,
    ) -> dict[str, Any]:
        """Invoke the Bedrock Converse API.

        :param messages: Conversation messages.
        :param model_id: Model alias (haiku, sonnet, opus) to use for this request.
        :param system_prompt: Optional system prompt.
        :param tool_config: Optional tool configuration for tool use.
        :param max_tokens: Maximum tokens in response.
        :param temperature: Sampling temperature (0.0 for deterministic).
        :param call_type: Type of call for tracking (chat or selector).
        :param cache_system_prompt: Enable prompt caching for system prompt.
        :returns: Converse API response.
        :raises BedrockClientError: If the API call fails.
        :raises ValueError: If model_id is not a valid alias.
        """
        effective_model = resolve_model_id(model_id)
        request_params: dict[str, Any] = {
            "modelId": effective_model,
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            system_blocks: list[dict[str, Any]] = [{"text": system_prompt}]
            if cache_system_prompt:
                system_blocks.append({"cachePoint": {"type": "default"}})
            request_params["system"] = system_blocks

        if tool_config:
            request_params["toolConfig"] = tool_config

        try:
            logger.debug(
                f"Calling Bedrock Converse: model={effective_model}, "
                f"messages_count={len(messages)}, cache_enabled={cache_system_prompt}"
            )
            start_time = time.perf_counter()
            response = self._client.converse(**request_params)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            usage = response.get("usage", {})
            cache_read = usage.get("cacheReadInputTokens", 0)
            cache_write = usage.get("cacheWriteInputTokens", 0)

            logger.debug(
                f"Bedrock response: stop_reason={response.get('stopReason')}, "
                f"usage={usage}, latency_ms={latency_ms}"
            )

            # Log cache effectiveness
            if cache_system_prompt and (cache_read > 0 or cache_write > 0):
                logger.info(f"Prompt cache: read={cache_read} tokens, write={cache_write} tokens")

            # Record call if tracking context is active
            response_dict = dict(response)
            tracking_context = get_tracking_context()
            if tracking_context is not None:
                tracking_context.record_call(
                    model_alias=model_id.lower(),
                    model_id=effective_model,
                    call_type=call_type,
                    request_messages=[dict(m) for m in messages],
                    response=response_dict,
                    latency_ms=latency_ms,
                )

            return response_dict

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.exception(f"Bedrock API error: code={error_code}, message={error_message}")
            raise BedrockClientError(
                f"Bedrock API call failed: {error_code} - {error_message}"
            ) from e

    def parse_tool_use(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool use blocks from a Converse response.

        :param response: Converse API response.
        :returns: List of tool use dictionaries with 'toolUseId', 'name', 'input'.
        """
        tool_uses: list[dict[str, Any]] = []
        output = response.get("output", {})
        message = output.get("message", {})
        content: list[ContentBlockTypeDef] = message.get("content", [])

        for block in content:
            if "toolUse" in block:
                tool_use = block["toolUse"]
                tool_uses.append(
                    {
                        "toolUseId": tool_use.get("toolUseId", ""),
                        "name": tool_use.get("name", ""),
                        "input": tool_use.get("input", {}),
                    }
                )

        return tool_uses

    def parse_text_response(self, response: dict[str, Any]) -> str:
        """Extract text content from a Converse response.

        :param response: Converse API response.
        :returns: Concatenated text content from the response.
        """
        output = response.get("output", {})
        message = output.get("message", {})
        content: list[ContentBlockTypeDef] = message.get("content", [])

        text_parts: list[str] = []
        for block in content:
            if "text" in block:
                text_parts.append(block["text"])

        return "\n".join(text_parts)

    def create_tool_result_message(
        self,
        tool_use_id: str,
        result: dict[str, Any],
        is_error: bool = False,
    ) -> MessageTypeDef:
        """Create a tool result message for the conversation.

        :param tool_use_id: ID of the tool use being responded to.
        :param result: Result data from the tool execution.
        :param is_error: Whether the result represents an error.
        :returns: Message with tool result content.
        """
        return {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": result}],
                        "status": "error" if is_error else "success",
                    }
                }
            ],
        }

    def create_user_message(self, text: str) -> MessageTypeDef:
        """Create a user message.

        :param text: Message text.
        :returns: User message dictionary.
        """
        return {"role": "user", "content": [{"text": text}]}

    def get_stop_reason(self, response: dict[str, Any]) -> str:
        """Extract stop reason from a Converse response.

        :param response: Converse API response.
        :returns: Stop reason string.
        """
        return str(response.get("stopReason", ""))

    def format_tool_use_as_json(self, tool_uses: list[dict[str, Any]]) -> str:
        """Format tool uses as JSON for logging/debugging.

        :param tool_uses: List of tool use dictionaries.
        :returns: JSON string representation.
        """
        return json.dumps(tool_uses, indent=2, default=str)
