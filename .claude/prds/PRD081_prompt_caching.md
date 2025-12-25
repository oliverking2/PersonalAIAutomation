# PRD 081: Prompt Caching

## Overview
Enable Bedrock prompt caching to reduce token costs by caching static prompt components (system instructions, standard tools).

---

## Problem Statement
The agent currently resends full system prompts and all tool definitions on every Bedrock call, leading to:
- Repeated token costs for identical content
- Higher per-message costs than necessary

---

## Goals
- Enable prompt caching for static content
- Reduce input token costs by 40%+ on repeated calls
- Validate caching is working via `cacheReadInputTokens`

---

## Non-Goals
- Context window management (see PRD082)
- Rolling summaries (see PRD082)
- Message sliding window (see PRD082)

---

## Target Prompt Structure

### Static (Cached)
These components are identical across calls and should be cached:
- System instructions
- **Standard tools** (always available, tagged with `standard`)
- Safety rules

### Dynamic
These components change per-request and are not cached:
- **Selected tools** (chosen by ToolSelector per request)
- Conversation messages
- Current run tool outputs

---

## Tool Categorisation

Tools are split into two categories for cost optimisation:

### Standard Tools (Cached)
Tools that are always available regardless of user intent. Included in the cached system prompt to avoid repeated token costs.

**Characteristics:**
- Tagged with `standard` in ToolRegistry
- Included in every agent run
- Cached as part of system prompt (paid once, reused)
- Examples: clarify, help, cancel, set_preference

**Registration:**
```python
registry.register(clarify_tool, tags={"standard"})
```

### Domain Tools (Dynamic)
Tools selected per-request based on user intent. Added dynamically to reduce context size.

**Characteristics:**
- Tagged by domain (e.g., `tasks`, `goals`, `reading`)
- Selected by ToolSelector using Haiku (cheap)
- Only relevant tools added to prompt
- Examples: query_tasks, create_goal, update_reading_item

**Selection flow:**
```
User message → ToolSelector (Haiku) → 3-5 domain tools selected
Final tools = Standard tools (cached) + Selected domain tools (dynamic)
```

### Cost Impact

| Tool Type | Tokens | Caching | Per-Request Cost |
|-----------|--------|---------|------------------|
| Standard (5 tools) | ~1,500 | Cached | Near zero (after first call) |
| Domain (5 selected) | ~1,500 | Not cached | Full cost |
| Domain (100 available) | ~30,000 | N/A | Avoided via selection |

**Savings:** Standard tools cached + only relevant domain tools included = 90%+ reduction vs sending all tools every call.

---

## Implementation

### Bedrock Prompt Caching
Bedrock supports prompt caching via cache control blocks. The system prompt and standard tools should be marked as cacheable.

**Key changes:**
1. Structure system prompt with cache control markers
2. Separate standard tools from dynamic tools in the request
3. Enable caching in `BedrockClient.converse()`

### Validation
- Check `cacheReadInputTokens > 0` in response usage
- Log cache hit/miss ratio
- Compare costs before and after

---

## Observability
- Log `cacheReadInputTokens` on each call
- Track cache hit rate over time
- Alert if cache hits drop unexpectedly

---

## Success Metrics
- `cacheReadInputTokens > 0` on subsequent calls
- 40%+ reduction in input token costs for repeated conversations
- No degradation in agent behaviour

---

## Risks
- Misconfigured caching yields no benefit
- Cache invalidation on prompt changes

---

## Implementation Milestones
1. Add cache control to system prompt structure
2. Separate standard tools into cached block
3. Enable caching in BedrockClient
4. Add cache metrics logging
5. Validate cost reduction