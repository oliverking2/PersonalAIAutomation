# PRD18: Bedrock toolUseId Validation

**Status: PROPOSED**

**Roadmap Reference**: AGENT-002 (Critical Priority)

## Overview

Validate Bedrock API responses upfront and raise clear errors when required fields like `toolUseId` are missing, instead of returning empty strings that cause confusing downstream failures.

## Problem Statement

Current implementation in `bedrock_client.py:175-191`:

```python
def parse_tool_use(self, response: dict) -> tuple[str, str, dict]:
    """Parse tool use from Bedrock response."""
    content = response.get("output", {}).get("message", {}).get("content", [])
    for block in content:
        if block.get("type") == "tool_use":
            tool_use_id = block.get("toolUseId", "")  # Returns "" if missing
            name = block.get("name", "")
            input_data = block.get("input", {})
            return tool_use_id, name, input_data
    return "", "", {}
```

**Problems**:
1. Missing `toolUseId` returns empty string `""`
2. Empty ID propagates through the system
3. Fails later with confusing error messages
4. No indication that Bedrock response was malformed
5. Debugging requires tracing through multiple layers

**Example Failure Chain**:
```
Bedrock returns: {"toolUseId": null, "name": "query_tasks", ...}
                        ↓
parse_tool_use returns: ("", "query_tasks", {...})
                        ↓
_handle_tool_use creates: {"tool_use_id": "", ...}
                        ↓
Next API call fails: "Invalid tool_use_id format"
```

## Proposed Solution

Validate response structure upfront and raise specific exceptions:

```python
# src/agent/bedrock_client.py

from src.agent.exceptions import BedrockResponseError


class BedrockClient:
    def parse_tool_use(self, response: dict[str, Any]) -> ToolUseBlock:
        """Parse tool use from Bedrock response.

        :param response: Raw Bedrock API response.
        :returns: Parsed tool use block.
        :raises BedrockResponseError: If response structure is invalid.
        """
        content = self._extract_content(response)

        for block in content:
            if block.get("type") == "tool_use":
                return self._validate_tool_use_block(block)

        raise BedrockResponseError(
            "No tool_use block found in Bedrock response",
            response=response,
        )

    def _validate_tool_use_block(self, block: dict[str, Any]) -> ToolUseBlock:
        """Validate and extract tool use block fields.

        :param block: Raw tool use block from response.
        :returns: Validated ToolUseBlock.
        :raises BedrockResponseError: If required fields missing.
        """
        tool_use_id = block.get("toolUseId")
        if not tool_use_id:
            raise BedrockResponseError(
                "Bedrock response missing required 'toolUseId' field",
                response=block,
                field="toolUseId",
            )

        name = block.get("name")
        if not name:
            raise BedrockResponseError(
                "Bedrock response missing required 'name' field",
                response=block,
                field="name",
            )

        return ToolUseBlock(
            id=tool_use_id,
            name=name,
            input=block.get("input", {}),
        )

    def _extract_content(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract content list from Bedrock response.

        :param response: Raw Bedrock API response.
        :returns: List of content blocks.
        :raises BedrockResponseError: If content path invalid.
        """
        try:
            output = response["output"]
            message = output["message"]
            content = message["content"]
            if not isinstance(content, list):
                raise BedrockResponseError(
                    "Bedrock response 'content' is not a list",
                    response=response,
                )
            return content
        except KeyError as e:
            raise BedrockResponseError(
                f"Bedrock response missing expected path: {e}",
                response=response,
            ) from e
```

## New Exception

```python
# src/agent/exceptions.py

class BedrockResponseError(Exception):
    """Raised when Bedrock API response is malformed or missing required fields."""

    def __init__(
        self,
        message: str,
        response: dict[str, Any] | None = None,
        field: str | None = None,
    ) -> None:
        """Initialise Bedrock response error.

        :param message: Human-readable error description.
        :param response: Raw response that caused the error (for debugging).
        :param field: Specific field that was missing or invalid.
        """
        super().__init__(message)
        self.response = response
        self.field = field

    def __str__(self) -> str:
        base = super().__str__()
        if self.field:
            return f"{base} (field: {self.field})"
        return base
```

## TypedDict for Tool Use Block

```python
# src/agent/types.py

from typing import TypedDict, Any


class ToolUseBlock(TypedDict):
    """Validated tool use block from Bedrock response."""

    id: str
    name: str
    input: dict[str, Any]
```

## Error Handling in Runner

```python
# src/agent/runner.py

def _process_response(self, response: dict) -> StepResult:
    """Process Bedrock response and handle tool use."""
    try:
        if self._has_tool_use(response):
            tool_use = self._client.parse_tool_use(response)
            return self._handle_tool_use(tool_use)
        else:
            return self._handle_text_response(response)
    except BedrockResponseError as e:
        logger.error(f"Invalid Bedrock response: {e}")
        # Return error to user rather than propagating bad state
        return StepResult(
            status="error",
            message=f"Received invalid response from AI: {e}",
        )
```

## Implementation Steps

1. Add `BedrockResponseError` to `src/agent/exceptions.py`
2. Add `ToolUseBlock` TypedDict to `src/agent/types.py`
3. Update `parse_tool_use` with validation logic
4. Add `_validate_tool_use_block` helper method
5. Add `_extract_content` helper method
6. Update `AgentRunner` to catch `BedrockResponseError`
7. Write unit tests for validation scenarios
8. Write tests for error message clarity

## Testing

```python
class TestParseToolUse(unittest.TestCase):
    def test_raises_on_missing_tool_use_id(self):
        """Test error raised when toolUseId missing."""
        response = {
            "output": {
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "query_tasks", "input": {}}
                    ]
                }
            }
        }
        client = BedrockClient()

        with self.assertRaises(BedrockResponseError) as ctx:
            client.parse_tool_use(response)

        self.assertIn("toolUseId", str(ctx.exception))

    def test_raises_on_null_tool_use_id(self):
        """Test error raised when toolUseId is null."""
        response = {
            "output": {
                "message": {
                    "content": [
                        {"type": "tool_use", "toolUseId": None, "name": "query_tasks"}
                    ]
                }
            }
        }
        client = BedrockClient()

        with self.assertRaises(BedrockResponseError) as ctx:
            client.parse_tool_use(response)

        self.assertIn("toolUseId", str(ctx.exception))

    def test_raises_on_malformed_response_structure(self):
        """Test error raised when response path invalid."""
        response = {"unexpected": "structure"}
        client = BedrockClient()

        with self.assertRaises(BedrockResponseError):
            client.parse_tool_use(response)

    def test_valid_response_parses_correctly(self):
        """Test valid response returns ToolUseBlock."""
        response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "toolUseId": "abc123",
                            "name": "query_tasks",
                            "input": {"status": "In Progress"},
                        }
                    ]
                }
            }
        }
        client = BedrockClient()

        result = client.parse_tool_use(response)

        self.assertEqual(result["id"], "abc123")
        self.assertEqual(result["name"], "query_tasks")
        self.assertEqual(result["input"], {"status": "In Progress"})
```

## Success Criteria

1. Missing `toolUseId` raises `BedrockResponseError` immediately
2. Error message clearly identifies the problem field
3. No empty strings propagate through the system
4. Debug information (raw response) available in exception
5. Agent runner handles error gracefully
6. Existing valid responses continue to work
