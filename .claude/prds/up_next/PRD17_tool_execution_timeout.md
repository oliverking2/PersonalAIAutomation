# PRD17: Tool Execution Timeout

**Status: PROPOSED**

**Roadmap Reference**: AGENT-001 (Critical Priority)

## Overview

Add configurable timeout to tool execution to prevent agent hangs when tools make blocking calls that never return.

## Problem Statement

Tool handlers in `AgentRunner._execute_tool()` can hang indefinitely:

```python
# Current implementation (runner.py:602-620)
def _execute_tool(self, tool_name: str, tool_input: dict) -> Any:
    handler = self._tools_dict[tool_name]
    return handler(tool_input)  # No timeout - can block forever
```

**Risk Scenarios**:
1. HTTP request to unresponsive API hangs
2. Database query on locked table blocks
3. External service timeout not configured
4. Network partition causes connection to stall

**Impact**: Agent run blocks permanently, requiring manual intervention. No way to recover or retry. User experience degrades significantly.

## Proposed Solution

Wrap tool execution with `concurrent.futures.ThreadPoolExecutor` and configurable timeout:

```python
# src/agent/runner.py

import concurrent.futures
from src.agent.config import AgentConfig

class AgentRunner:
    def __init__(self, config: AgentConfig = DEFAULT_CONFIG):
        self._config = config
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool handler with timeout protection.

        :param tool_name: Name of the tool to execute.
        :param tool_input: Input parameters for the tool.
        :returns: Tool execution result.
        :raises ToolTimeoutError: If execution exceeds timeout.
        :raises ToolExecutionError: If tool raises an exception.
        """
        handler = self._tools_dict[tool_name]
        future = self._executor.submit(handler, tool_input)

        try:
            result = future.result(timeout=self._config.tool_timeout_seconds)
            return result
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise ToolTimeoutError(
                f"Tool '{tool_name}' exceeded {self._config.tool_timeout_seconds}s timeout"
            )
        except Exception as e:
            raise ToolExecutionError(f"Tool '{tool_name}' failed: {e}") from e
```

## New Exceptions

```python
# src/agent/exceptions.py

class ToolTimeoutError(Exception):
    """Raised when tool execution exceeds configured timeout."""

    def __init__(self, message: str, tool_name: str | None = None) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class ToolExecutionError(Exception):
    """Raised when tool execution fails with an exception."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.original_error = original_error
```

## Handling Timeout in Agent Loop

When a tool times out, return an error result to the LLM so it can retry or use a different approach:

```python
def _handle_tool_use(self, tool_use: ToolUseBlock) -> ToolResultBlock:
    """Handle a single tool use request."""
    tool_name = tool_use["name"]
    tool_input = tool_use["input"]

    try:
        result = self._execute_tool(tool_name, tool_input)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use["id"],
            "content": json.dumps(result),
        }
    except ToolTimeoutError as e:
        logger.warning(f"Tool timeout: {e}")
        return {
            "type": "tool_result",
            "tool_use_id": tool_use["id"],
            "content": json.dumps({
                "error": str(e),
                "error_type": "timeout",
                "suggestion": "The operation took too long. Try a simpler query or different approach.",
            }),
            "is_error": True,
        }
    except ToolExecutionError as e:
        logger.error(f"Tool execution error: {e}")
        return {
            "type": "tool_result",
            "tool_use_id": tool_use["id"],
            "content": json.dumps({
                "error": str(e),
                "error_type": "execution_error",
            }),
            "is_error": True,
        }
```

## Configuration

Default timeout: **30 seconds**

Override via:
1. `AgentConfig(tool_timeout_seconds=60)`
2. Environment variable: `AGENT_TOOL_TIMEOUT=60`

### Per-Tool Timeout (Future Enhancement)

For tools with known long execution times:

```python
@dataclass
class ToolDef:
    name: str
    description: str
    handler: Callable
    input_schema: dict
    timeout_seconds: int | None = None  # Override default if set
```

## Implementation Steps

1. Add `ToolTimeoutError` and `ToolExecutionError` to `src/agent/exceptions.py`
2. Add `tool_timeout_seconds` to `AgentConfig` (PRD16 dependency)
3. Create `ThreadPoolExecutor` in `AgentRunner.__init__`
4. Wrap `_execute_tool` with timeout handling
5. Update `_handle_tool_use` to catch and convert timeout errors
6. Add cleanup in `AgentRunner.__del__` or context manager
7. Write unit tests for timeout behaviour
8. Write integration test with slow mock tool

## Testing

```python
class TestToolTimeout(unittest.TestCase):
    def test_tool_times_out_after_configured_seconds(self):
        """Test tool execution respects timeout."""
        def slow_tool(input: dict) -> dict:
            time.sleep(10)
            return {"result": "done"}

        config = AgentConfig(tool_timeout_seconds=1)
        runner = AgentRunner(config=config)
        runner._tools_dict["slow_tool"] = slow_tool

        with self.assertRaises(ToolTimeoutError):
            runner._execute_tool("slow_tool", {})

    def test_timeout_error_returned_to_llm(self):
        """Test timeout produces error tool result for LLM."""
        # ... test that LLM receives actionable error message
```

## Thread Safety Considerations

1. **Single worker**: `ThreadPoolExecutor(max_workers=1)` ensures sequential tool execution
2. **Executor lifecycle**: Create executor per `AgentRunner` instance
3. **Cleanup**: Shutdown executor in `__del__` or use context manager pattern
4. **Future cancellation**: Call `future.cancel()` on timeout (best effort)

## Alternatives Considered

### signal.alarm (Unix only)
- Pros: Simple, no threads
- Cons: Not cross-platform, can't interrupt blocking I/O

### asyncio.wait_for
- Pros: Native async timeout
- Cons: Requires async tool handlers, significant refactor

### multiprocessing
- Pros: True isolation, can kill hung processes
- Cons: Serialisation overhead, complex IPC

**Decision**: `ThreadPoolExecutor` provides good balance of simplicity, cross-platform support, and minimal refactoring.

## Success Criteria

1. Tool execution respects configured timeout
2. Timeout produces actionable error for LLM
3. Agent run recovers from hung tools
4. No resource leaks from cancelled futures
5. Existing tests pass without modification
