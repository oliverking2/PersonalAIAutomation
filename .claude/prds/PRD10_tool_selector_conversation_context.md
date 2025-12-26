# PRD10: Tool Selector Conversation Context

**Status: IMPLEMENTED (Context-Aware Additive Selection)**

## Problem Statement

The tool selector currently only sees the **current user message** when deciding which tools to select. This causes issues when:

1. **Clarification responses**: User provides details requested by the agent (e.g., "both work and due 1st jan") but the selector sees this as a new query
2. **Multi-turn task completion**: User is in the middle of a task flow but their short response gets misinterpreted
3. **Confirmation with followup**: User confirms and adds a new request, but selector only sees the new request

### Example Failure

```
User: "Add 2 tasks, one for tidying emails and one for unsubscribing"
Agent: "I need more details - due date and task group for each?"
User: "both work and both due 1st jan"
                ↓
Tool Selector sees: "both work and both due 1st jan"
Tool Selector picks: query_tasks (thinks it's a query for work tasks due Jan 1st)
                ↓
LLM tries to use create_task (based on conversation context)
But create_task isn't available → ERROR
```

## Proposed Solutions

### Option 1: Pass Conversation Summary to Tool Selector
- Include a brief summary of the conversation context with the current message
- Tool selector prompt becomes: "Given this conversation context: {summary}, and the user's message: {message}, select tools..."
- **Pros**: Selector has full context
- **Cons**: More tokens, higher latency, may still misinterpret

### Option 2: Sticky Tool Selection with Intent Detection
- Keep selected tools across turns unless intent clearly changes
- Add explicit intent change detection (separate from confirmation classification)
- **Pros**: Faster, tools stay consistent within a task flow
- **Cons**: Need reliable intent change detection

### Option 3: Hybrid - Context-Aware Re-selection
- On each turn, check if the message is:
  - A **clarification/detail** → Keep current tools
  - A **new request** → Re-select tools
  - A **confirmation** → Already handled by classifier
- Use a lightweight classifier to determine message type
- **Pros**: Best of both worlds
- **Cons**: Additional LLM call or heuristic complexity

### Option 4: Always Include Previously Selected Tools
- When re-selecting, always include the previously selected tools as candidates
- Selector can add more tools but never removes context-relevant ones
- **Pros**: Simple, backwards compatible
- **Cons**: May accumulate irrelevant tools over long conversations

## Recommendation

**Option 3 (Hybrid)** with a simple heuristic first:
1. If conversation has pending context (previous tools selected, no confirmation pending), check if message is likely a clarification
2. Heuristics for clarification: short message, contains keywords like "both", "yes", "that's right", references previous context
3. If clarification detected, keep current tools
4. If new request detected (longer message, new verbs like "add", "create", "show"), re-select

Fall back to **Option 1** (pass summary) if heuristics prove unreliable.

## Implementation Notes

- Location: `src/agent/runner.py:_resolve_tools()` and `src/agent/tool_selector.py`
- Consider adding `is_clarification()` helper or extending `ToolSelector.select()` to accept context
- May need conversation state to track "in-progress task flow"

## Success Criteria

1. User can provide clarifying details without tool re-selection breaking the flow
2. User can still change intent mid-conversation and get correct tools
3. No increase in latency for simple clarification responses
