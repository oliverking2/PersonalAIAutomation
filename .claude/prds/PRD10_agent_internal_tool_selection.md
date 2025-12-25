# PRD: Agent Internal Tool Selection

## Overview

Refactor AgentRunner to handle tool selection internally, providing a simpler API while optimising for cost at scale (100+ tools).

## Current State

```python
# Two separate steps required
selector = ToolSelector(registry=registry, client=bedrock)
selection = selector.select("Show me my high priority tasks")

runner = AgentRunner(registry=registry, client=bedrock)
result = runner.run("Show me my high priority tasks", selection.tool_names)
```

## Target State

```python
# Single entry point
runner = AgentRunner(registry=registry, client=bedrock)
result = runner.run("Show me my high priority tasks")
```

## Cost Justification

At 100 tools with ~300 tokens per tool schema:

| Approach | Input Tokens per Request | Relative Cost |
|----------|--------------------------|---------------|
| All tools every call | ~120,000 | 100% |
| Selection + subset | ~12,000 | 10% |

**90% cost reduction** by using two-phase approach with cheap selection model.

## Design

### Architecture

```
AgentRunner.run(message)
    │
    ├─► ToolSelector.select(message)     [Haiku - cheap]
    │       └─► Returns: ["tool_a", "tool_b", ...]
    │
    └─► Execution Loop                    [Sonnet - capable]
            └─► Uses only selected tools
```

### Model Selection

| Phase | Model | Rationale |
|-------|-------|-----------|
| Tool Selection | Haiku | Classification task, cheap ($0.25/1M tokens) |
| Execution | Sonnet | Complex reasoning, tool use ($3/1M tokens) |

### Standard vs Domain Tools

See PRD08 for full context. Summary:

- **Standard tools**: Tagged with `standard`, always included, cached in system prompt
- **Domain tools**: Tagged by domain, selected per-request by ToolSelector

```
Final tools = Standard tools (from cache) + Selected domain tools (dynamic)
```

**ToolRegistry methods:**
- `get_standard_tools()` → tools tagged with `standard`
- `get_selectable_tools()` → tools NOT tagged with `standard`

### API Changes

**AgentRunner.__init__()**
- Add `selector_model` parameter (default: Haiku model ID)
- Create internal ToolSelector instance
- Cache standard tools from registry

**AgentRunner.run()**
- Remove `tool_names` parameter (was required)
- Add optional `tool_names` parameter for override/testing
- Internally call ToolSelector if no override provided
- Merge standard tools with selected tools

**ToolSelector**
- Add `model` parameter to `select()` method
- Exclude standard tools from selection candidates (they're always included)

**ToolRegistry**
- Add `get_standard_tools()` method
- Add `get_selectable_tools()` method

**BedrockClient**
- Support model override per call (already supports this)

## Implementation

### Phase 1: AgentRunner Changes

```python
class AgentRunner:
    def __init__(
        self,
        registry: ToolRegistry,
        client: BedrockClient,
        selector_model: str = "haiku",  # New
        max_steps: int = 5,
    ) -> None:
        self._registry = registry
        self._client = client
        self._selector = ToolSelector(registry=registry, client=client)
        self._selector_model = selector_model
        self._max_steps = max_steps

    def run(
        self,
        message: str,
        tool_names: list[str] | None = None,  # Now optional
    ) -> AgentRunResult:
        # Auto-select if not provided
        if tool_names is None:
            selection = self._selector.select(message, model=self._selector_model)
            tool_names = selection.tool_names

        # Continue with execution loop...
```

### Phase 2: ToolSelector Model Parameter

```python
class ToolSelector:
    def select(
        self,
        user_intent: str,
        model: str | None = None,  # Override default
    ) -> ToolSelectionResult:
        # Use specified model or default
```

### Phase 3: BedrockClient Model Override

Ensure `converse()` accepts model override (already implemented).

## Checklist

- [x] Add `get_standard_tools()` and `get_selectable_tools()` to ToolRegistry
- [x] Add `selector_model` parameter to AgentRunner
- [x] Make `tool_names` optional in `AgentRunner.run()`
- [x] Create ToolSelector internally in AgentRunner
- [x] Merge standard tools with selected tools in execution
- [x] Add `model` parameter to `ToolSelector.select()`
- [x] Exclude standard tools from ToolSelector candidates
- [x] Update BedrockClient to support Haiku model ID
- [x] Update tests for new API (both with and without tool override)
- [x] Update README usage examples

## Success Criteria

- Single-line agent invocation: `runner.run("message")`
- Tool override still works for testing: `runner.run("message", tool_names=[...])`
- ToolSelector uses Haiku by default
- Execution loop continues using Sonnet
- All existing tests pass (with updates)
- 90% token reduction at 100 tools (theoretical)
