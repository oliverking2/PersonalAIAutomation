# PRD31: Agent Module Cleanup

**Status: BACKLOG**

**Roadmap References**: AGENT-009, AGENT-013, AGENT-015, AGENT-017, AGENT-020

## Overview

A collection of small improvements and fixes to the agent module focused on code cleanup, error handling consistency, and observability.

## Items

### 1. AGENT-009: Remove synthetic "I understand" message from context

**Current State**:
```python
# src/agent/utils/context_manager.py:296-302
assistant_ack = {
    "role": "assistant",
    "content": [{"text": "I understand the previous context. How can I help you?"}],
}
messages.append(summary_message)
messages.append(assistant_ack)
```

**Problem**: This synthetic message wastes tokens and doesn't add value. The summary already provides context; adding a filler response is unnecessary. Modern Claude models don't need this kind of scaffolding.

**Solution**: Remove the synthetic assistant acknowledgement. The summary message alone is sufficient context:
```python
if state.summary:
    summary_message = {
        "role": "user",
        "content": [
            {
                "text": (
                    f"[Previous conversation summary: {state.summary}]\n\n"
                    "Continue from this context."
                )
            }
        ],
    }
    messages.append(summary_message)
```

**Files**: `src/agent/utils/context_manager.py`

---

### 2. AGENT-013: Validate `tool_names` is a list in selector response

**Current State**:
```python
# src/agent/utils/tools/selector.py:221-227
domains = data.get("domains", [])
reasoning = data.get("reasoning", "")

# Filter to valid domains...
valid_domains = list(dict.fromkeys(d for d in domains if d in available_domains))
```

**Problem**: If the LLM returns `"domains": "domain:tasks"` (a string instead of a list), the code will iterate over characters, not domain names. This could lead to confusing bugs.

**Solution**: Add explicit type validation:
```python
domains = data.get("domains", [])
if not isinstance(domains, list):
    raise ToolSelectionError(
        f"Expected 'domains' to be a list, got {type(domains).__name__}"
    )
reasoning = data.get("reasoning", "")
```

**Files**: `src/agent/utils/tools/selector.py`

---

### 3. AGENT-015: Standardise error return formats in tools

**Current State**: Error formats vary across tools:
```python
# factory.py:345
{"error": "No properties to update", "updated": False}

# runner.py:785-790 (timeout)
{"error": str(e), "error_type": "timeout", "suggestion": "..."}

# runner.py:793-794 (execution error)
{"error": e.error}
```

**Problem**: Inconsistent error formats make it harder for the LLM to handle errors uniformly and for developers to debug issues.

**Solution**: Define a standard error response format and apply it consistently:
```python
# Standard error format
{
    "error": str,           # Required: human-readable error message
    "error_type": str,      # Required: categorised error type
    "suggestion": str | None,  # Optional: actionable suggestion
}

# Error types enum
class ToolErrorType(StrEnum):
    VALIDATION = "validation"      # Invalid arguments
    NOT_FOUND = "not_found"        # Entity not found
    TIMEOUT = "timeout"            # Operation timed out
    EXECUTION = "execution"        # General execution failure
    PERMISSION = "permission"      # Auth/permission error
    RATE_LIMIT = "rate_limit"      # Rate limit exceeded
```

**Files**:
- `src/agent/enums.py` (add ToolErrorType)
- `src/agent/runner.py` (standardise error returns)
- `src/agent/tools/factory.py` (standardise error returns)

---

### 4. AGENT-017: Add request ID propagation to API client

**Current State**: `InternalAPIClient` doesn't propagate request IDs, making it hard to trace requests across services.

**Problem**: When debugging issues, there's no way to correlate agent tool calls with API server logs.

**Solution**: Generate and propagate request IDs via headers:
```python
class InternalAPIClient:
    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        request_id = str(uuid.uuid4())
        headers = {"X-Request-ID": request_id}

        logger.debug(
            f"API request: {method} {path} request_id={request_id}"
        )
        # ... rest of request logic
```

Also update the API server to log incoming request IDs from the `X-Request-ID` header.

**Files**:
- `src/api/client.py` (add request ID generation and header)
- `src/api/app.py` (add middleware to log request IDs)

---

### 5. AGENT-020: Improve BedrockClient error context

**Current State**:
```python
# src/agent/bedrock_client.py:180-186
except ClientError as e:
    error_code = e.response.get("Error", {}).get("Code", "Unknown")
    error_message = e.response.get("Error", {}).get("Message", str(e))
    logger.exception(f"Bedrock API error: code={error_code}, message={error_message}")
    raise BedrockClientError(
        f"Bedrock API call failed: {error_code} - {error_message}"
    ) from e
```

**Problem**: Error logs don't include request context (model, message count, call type), making debugging harder.

**Solution**: Include request context in error logs:
```python
except ClientError as e:
    error_code = e.response.get("Error", {}).get("Code", "Unknown")
    error_message = e.response.get("Error", {}).get("Message", str(e))
    logger.exception(
        f"Bedrock API error: code={error_code}, message={error_message}, "
        f"model={effective_model}, messages_count={len(messages)}, "
        f"call_type={call_type.value}"
    )
    raise BedrockClientError(
        f"Bedrock API call failed: {error_code} - {error_message}"
    ) from e
```

**Files**: `src/agent/bedrock_client.py`

---

## Implementation Order

These items are independent and can be implemented in any order. Suggested grouping:

1. **Validation** (AGENT-013) - Quick win, prevents edge case bugs
2. **Token optimisation** (AGENT-009) - Simple removal, saves tokens per conversation
3. **Error handling** (AGENT-015) - Requires more thought on error types
4. **Observability** (AGENT-017, AGENT-020) - Improves debugging

## Success Criteria

1. No synthetic "I understand" message in context (AGENT-009)
2. Selector validates `domains` is a list (AGENT-013)
3. All tool errors use consistent format with error_type (AGENT-015)
4. API requests include X-Request-ID header (AGENT-017)
5. Bedrock errors include request context in logs (AGENT-020)
6. All existing tests pass
7. `make check` passes (lint, format, types, coverage)

## Testing Requirements

Each item needs minimal test updates:

- **AGENT-009**: Update context_manager tests to not expect synthetic message
- **AGENT-013**: Add test for string domains handling
- **AGENT-015**: Add tests for standardised error format
- **AGENT-017**: Add test verifying X-Request-ID header is sent
- **AGENT-020**: Update error logging tests to verify context
