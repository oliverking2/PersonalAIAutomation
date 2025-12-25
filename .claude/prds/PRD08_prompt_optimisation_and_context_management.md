# PRD 02: Prompt Optimisation and Context Window Management

## Overview
This PRD defines changes to reduce token growth and cost by optimising prompt construction and managing conversational context.

---

## Problem Statement
The agent currently resends full conversation history and tool definitions on every Bedrock call, leading to:
- linear token growth
- increasing cost per message
- eventual context window exhaustion

---

## Goals
- Cap context growth deterministically
- Reduce input token cost
- Preserve reasoning quality
- Prepare for long-running conversations

---

## Non-Goals
- Vector memory or embeddings
- Cross-user memory reuse
- Bedrock Agents migration

---

## Target Prompt Structure

### Static (Cached)
- System instructions
- **Standard tools** (always available, tagged with `standard`)
- Safety rules

### Dynamic
- **Selected tools** (chosen by ToolSelector per request)
- Rolling summary
- Last N messages (10–15)
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

## Design

### Sliding Window
- Retain last 10–15 messages
- Drop older raw turns after summarisation

### Rolling Summary
- Summarise dropped messages
- Persist summary per conversation
- Enforce max size (eg 300–500 tokens)

### Prompt Caching
- Mark static prompt blocks as cacheable
- Validate via cacheReadInputTokens > 0

---

## Data Model Additions

### conversation_memory
| Field | Type | Notes |
|-----|-----|------|
| conversation_id | UUID | PK/FK |
| summary | text | rolling summary |
| updated_at | timestamptz | |

---

## Behavioural Flow
1. Load summary and recent messages
2. Build layered prompt
3. Execute agent run
4. Update summary post-run

---

## Guardrails
- Hard caps on message count and summary size
- Fallback if prompt exceeds threshold

---

## Observability
- Log summary token size
- Log cache read tokens
- Compare pre and post optimisation costs

---

## Success Metrics
- At least 40 percent reduction in input tokens
- Stable agent behaviour
- No context window overflow

---

## Risks
- Poor summaries degrade memory
- Misconfigured caching yields no benefit

---

## Implementation Milestones
1. Prompt refactor
2. Summary generation logic
3. DB persistence
4. Cache enablement
5. Cost comparison validation
