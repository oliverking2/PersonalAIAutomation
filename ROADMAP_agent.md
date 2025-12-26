# Agent Module Roadmap

This document tracks improvements and technical debt for the `src/agent/` module.

## Critical Priority

### AGENT-001: Add tool execution timeout
- **Location**: `runner.py:602-620` (`_execute_tool`)
- **Issue**: Tool handlers can hang indefinitely with no timeout mechanism
- **Risk**: Agent can hang permanently on a stuck tool
- **Solution**: Wrap execution with `concurrent.futures.ThreadPoolExecutor` or `signal.alarm`
- **Effort**: Small

### AGENT-002: Fix unsafe toolUseId handling
- **Location**: `bedrock_client.py:175-191` (`parse_tool_use`)
- **Issue**: Returns empty string for missing `toolUseId` which causes downstream failures
- **Risk**: Silent failures when Bedrock response is malformed
- **Solution**: Validate structure upfront and raise `BedrockClientError` with clear message
- **Effort**: Small

## High Priority

### AGENT-003: Extract duplicate tool patterns into factory
- **Location**: `tools/tasks.py`, `tools/goals.py`, `tools/reading_list.py`
- **Issue**: ~180 lines duplicated across three files with identical patterns:
  - `_get_client()` function identical in all three
  - `query_*()`, `get_*()`, `create_*()`, `update_*()` nearly identical
  - Tool definition generation with dynamic descriptions
- **Solution**: Create generic tool factory:
  ```python
  def create_crud_tools(
      domain: str,
      data_source_env: str,
      create_model: type[BaseModel],
      update_model: type[BaseModel],
  ) -> list[ToolDef]:
      """Generate query/get/create/update tools for a domain."""
  ```
- **Effort**: Medium

### AGENT-004: Fix HTTP connection pooling for tool handlers
- **Location**: `tools/*.py` - `_get_client()` functions
- **Issue**: Each tool call creates fresh `AgentAPIClient` with new `requests.Session`. No connection reuse.
- **Risk**: Significant HTTP overhead with many tool calls
- **Solution**: Module-level singleton or dependency injection:
  ```python
  _api_client: AgentAPIClient | None = None

  def get_shared_client() -> AgentAPIClient:
      global _api_client
      if _api_client is None:
          _api_client = AgentAPIClient(...)
      return _api_client
  ```
- **Effort**: Small

### AGENT-005: Add message size limits to conversation state
- **Location**: `context_manager.py:100-115` (`append_messages`)
- **Issue**: Messages appended without size check. Could cause memory exhaustion before sliding window triggers.
- **Solution**: Add `max_message_bytes` parameter and check total size before appending
- **Effort**: Small

### AGENT-006: Fix unknown tool infinite loop
- **Location**: `runner.py:458-460` (`_handle_unknown_tool`)
- **Issue**: When LLM requests unknown tool, error is added but tool remains in available list. LLM can repeatedly request it.
- **Solution**: Track failed tool requests and either remove from available tools or add explicit "tool not available" instruction to next prompt
- **Effort**: Small

## Medium Priority

### AGENT-007: Fix loose message typing
- **Location**: `runner.py:86` (`_RunState.messages`)
- **Issue**: Typed as `list[Any]` with comment saying it's `MessageTypeDef`. Defeats mypy's purpose.
- **Solution**: Change to `list[MessageTypeDef]` and fix any resulting type errors
- **Effort**: Small

### AGENT-008: Validate classification response type
- **Status**: COMPLETED
- **Location**: `confirmation_classifier.py:128-140` (`_parse_classification_response`)
- **Resolution**: Added robust error handling with retries and markdown extraction. Now raises `ClassificationParseError` on failure instead of silently defaulting.

### AGENT-009: Remove fake assistant acknowledgement
- **Location**: `context_manager.py:268-285` (`build_context_messages`)
- **Issue**: Injects hardcoded "I understand the previous context" message that isn't real. Could confuse the LLM or pollute conversation history.
- **Solution**: Either remove the fake message or use a different mechanism (system message, metadata field)
- **Effort**: Small

### AGENT-010: Add rate limiting and backoff
- **Location**: `bedrock_client.py:130`, `api_client.py:115`
- **Issue**: No backoff or rate limiting for API calls. Could hit quota limits and cause cascading failures.
- **Solution**: Add exponential backoff with jitter using `tenacity` or custom retry logic
- **Effort**: Medium

### AGENT-011: Validate model configuration at init time
- **Location**: `runner.py:146-149`
- **Issue**: Invalid model alias from environment variable only caught at first API call, not at initialisation.
- **Solution**: Validate `AGENT_SELECTOR_MODEL` and `AGENT_CHAT_MODEL` in `AgentRunner.__init__`
- **Effort**: Small

### AGENT-012: Fix state corruption on NEW_INTENT
- **Status**: COMPLETED
- **Location**: `runner.py:320-322`
- **Resolution**: Removed tool reuse logic entirely - now always re-selects tools on each turn based on current message. This handles mid-conversation intent changes naturally.

### AGENT-013: Validate tool selector response structure
- **Location**: `tool_selector.py:84-122` (`_parse_selection_response`)
- **Issue**: Doesn't validate that `tool_names` is actually a list. If response is `{"tool_names": "string"}`, it won't error immediately but will fail later.
- **Solution**: Add `isinstance(tool_names, list)` check after JSON parsing
- **Effort**: Small

## Low Priority (Code Quality)

### AGENT-014: Refactor context_manager into class-based API
- **Location**: `context_manager.py`
- **Issue**: Multiple functions with complex interdependencies. Combines loading, saving, window management, summarisation. No clear contract for what each function assumes about state.
- **Solution**: Wrap in a class with clear invariants:
  ```python
  class ConversationContext:
      def __init__(self, conversation: AgentConversation): ...
      def append(self, messages: list[dict]) -> None: ...
      def apply_window(self, client: BedrockClient) -> None: ...
      def save(self, session: Session) -> None: ...
  ```
- **Effort**: Medium

### AGENT-015: Standardise error return formats in tools
- **Location**: `tools/*.py` handlers
- **Issue**: Inconsistent error responses - some return `{"error": ..., "updated": False}`, others just `{"error": ...}`
- **Solution**: Define standard error response schema and apply consistently
- **Effort**: Small

### AGENT-016: Centralise configuration constants
- **Location**: Multiple files
- **Issue**: Constants scattered across files:
  - `DEFAULT_MAX_STEPS` in `runner.py`
  - `DEFAULT_WINDOW_SIZE`, `DEFAULT_BATCH_THRESHOLD` in `context_manager.py`
  - `MODEL_PRICING` in `pricing.py`
  - `MAX_CLASSIFICATION_RETRIES` in `confirmation_classifier.py`
- **Solution**: Create `src/agent/config.py`:
  ```python
  class AgentConfig:
      max_steps: int = 5
      window_size: int = 15
      batch_threshold: int = 5
      tool_timeout_seconds: int = 30
      max_classification_retries: int = 2
  ```
- **Effort**: Medium

### AGENT-017: Add request ID propagation
- **Location**: Runner and API client
- **Issue**: Tracking context has `run_id` but it's not propagated to API client. Can't correlate API logs with agent run logs.
- **Solution**: Pass `run_id` to `AgentAPIClient` and include in request headers (e.g., `X-Request-ID`)
- **Effort**: Small

### AGENT-018: Optimise tracking data storage
- **Location**: `call_tracking.py:89` (`response_content`)
- **Issue**: Stores entire Bedrock response including potentially large content. Could cause database bloat over time.
- **Solution**: Store only usage/cost metadata, or compress response content, or add TTL for old records
- **Effort**: Medium

### AGENT-019: Filter PII from logs
- **Location**: `api_client.py:114`
- **Issue**: Logs full request JSON without filtering. If JSON contains sensitive data, it's logged.
- **Solution**: Add PII filter or redact known sensitive fields before logging
- **Effort**: Medium

### AGENT-020: Improve BedrockClient error context
- **Location**: `bedrock_client.py:161-167`
- **Issue**: Assumes `e.response` is always present. Error message extraction could fail if response structure is unexpected.
- **Solution**: Add defensive checks for response structure
- **Effort**: Small

### AGENT-021: Fix context_manager unused session parameter
- **Status**: COMPLETED
- **Location**: `context_manager.py:39` (`load_conversation_state`)
- **Resolution**: Removed unused `session` parameter

## Future Enhancements

### AGENT-F01: Async tool execution
- **Description**: Convert tool handlers to async for better concurrency
- **Benefit**: Could execute independent tools in parallel
- **Effort**: Large

### AGENT-F02: Tool result caching
- **Description**: Cache read-only tool results (query, get) within a conversation
- **Benefit**: Reduce API calls for repeated queries
- **Effort**: Medium

### AGENT-F03: Streaming responses
- **Description**: Support streaming Bedrock responses for real-time output
- **Benefit**: Better UX for long responses
- **Effort**: Large

### AGENT-F04: Tool usage analytics
- **Description**: Track which tools are used most, success rates, latencies
- **Benefit**: Identify problematic tools, optimise prompts
- **Effort**: Medium

### AGENT-F05: Dynamic tool loading
- **Description**: Load tools from configuration or plugins instead of hardcoded
- **Benefit**: Easier to add/modify tools without code changes
- **Effort**: Large

## Completed

| ID        | Description                                                                                                 | Date       |
|-----------|-------------------------------------------------------------------------------------------------------------|------------|
| AGENT-008 | Validate classification response - added retries, markdown handling, proper error raising                   | 2024-12-25 |
| AGENT-012 | Tool re-selection - removed reuse logic, always re-select tools on each turn based on current message       | 2024-12-25 |
| AGENT-021 | Remove unused session parameter from load_conversation_state                                                | 2024-12-25 |
| AGENT-022 | Add BedrockClient helper methods (create_assistant_tool_use_message, extract_json_from_markdown)            | 2024-12-25 |
| AGENT-023 | Refactor AgentRunner - extract _build_tool_config, _build_tools_dict, _execute_and_create_tool_call helpers | 2024-12-25 |
| AGENT-024 | Remove unused parameters (confirmed_tool_use_ids, tool_names from _handle_confirmation_response)            | 2024-12-25 |
| AGENT-025 | Fix HITL confirmation flow - execute confirmed tool directly instead of re-calling LLM                      | 2024-12-25 |
| AGENT-026 | Add today's date to system prompt for relative date handling (e.g., "end of week", "next Friday")           | 2024-12-25 |
| AGENT-027 | Include user confirmation message in conversation so LLM sees followup requests (e.g., "yes, and also X")   | 2024-12-25 |
| AGENT-028 | Handle multiple tool uses in response - provide error results for ALL when any is unknown                   | 2024-12-25 |
| AGENT-029 | Context-aware additive tool selection - selector considers current tools, only adds when needed             | 2024-12-25 |

## Priority Legend

- **Critical**: Could cause system failure or data loss
- **High**: Significant impact on reliability or performance
- **Medium**: Improves robustness or developer experience
- **Low**: Code quality and maintainability improvements
- **Future**: Nice-to-have enhancements for later consideration
