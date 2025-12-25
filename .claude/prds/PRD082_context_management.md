# PRD 082: Context Window Management

## Overview
Manage conversational context to prevent context window exhaustion in long-running conversations by implementing sliding windows, rolling summaries, and stateful conversation handling including confirmation flows.

---

## Problem Statement
In multi-turn conversations (especially via Telegram), the agent has several issues:

1. **Context growth**: Messages accumulate leading to token growth and eventual context window exhaustion
2. **Stateless confirmations**: The `AgentRunner` is currently stateless - each `run()` call starts fresh, breaking confirmation flows
3. **Natural language confirmations**: Users respond with natural language ("sure", "yep", "no stop") not boolean yes/no

---

## Goals
- Cap context growth deterministically
- Preserve reasoning quality across long conversations
- Support long-running Telegram conversations
- Enable stateful confirmation flows that preserve conversation context
- Handle natural language confirmation responses

---

## Non-Goals
- Vector memory or embeddings
- Cross-user memory reuse
- Bedrock Agents migration
- Prompt caching (see PRD081)

---

## Prerequisites
- PRD081 (Prompt Caching) implemented
- Telegram chat integration (PRD03) implemented

---

## Design

### Sliding Window
- Retain last 10–15 messages in full
- Drop older raw turns after summarisation
- Configurable window size

### Rolling Summary
- Summarise dropped messages using a cheap model (Haiku)
- Persist summary per conversation
- Enforce max size (300–500 tokens)
- Update summary after each agent run that drops messages

### Prompt Assembly
```
[Cached: System + Standard Tools]
[Rolling Summary of older context]
[Last N messages]
[Dynamic: Selected Tools]
[Current run tool outputs]
```

---

## Stateful Conversation Handling

### Current Problem
The `AgentRunner` is stateless. Each `run()` call:
- Re-runs tool selection from scratch
- Starts with fresh messages (no history)
- Creates a new agent run record

This breaks the confirmation flow:
```
User: "Add a task to read AWS docs"
Agent: [selects create_task] → "Confirm: Create task 'Read AWS docs'?"
User: "yep sounds good"
Agent: [NEW run()] → [RE-selects tools for "yep sounds good"] → Lost context!
```

### Solution: Conversation State

Introduce a `ConversationState` that persists across runs:

```python
@dataclass
class ConversationState:
    conversation_id: UUID
    messages: list[MessageTypeDef]  # Full message history
    selected_tools: list[str]       # Tools selected for current flow
    pending_confirmation: PendingConfirmation | None  # If awaiting confirmation
    summary: str | None             # Rolling summary of older messages
```

### Confirmation Flow with State

When confirmation is required:
1. Store state with `pending_confirmation` containing tool details
2. Return result with `stop_reason="confirmation_required"`
3. On next message, detect it's a confirmation response (not new intent)
4. Resume from stored state with confirmed tool

### Natural Language Confirmation Detection

Users won't send boolean yes/no. The agent must interpret natural language:

**Affirmative examples:**
- "yes", "yep", "sure", "sounds good", "go ahead", "do it", "ok"

**Negative examples:**
- "no", "stop", "cancel", "don't", "wait", "actually no", "never mind"

**Ambiguous (treat as new intent):**
- "actually, can you also...", "what about...", "show me the tasks first"

**Detection approach:**
Use Haiku to classify the response when `pending_confirmation` exists:

```python
def classify_confirmation_response(message: str) -> ConfirmationType:
    """Classify user response as confirm, deny, or new_intent."""
    # Use cheap Haiku call to classify
    # Returns: CONFIRM | DENY | NEW_INTENT
```

If `NEW_INTENT`, process as normal new request (clear pending confirmation).

### Updated Run Flow

```python
def run(self, user_message: str, conversation_id: UUID) -> AgentRunResult:
    state = load_conversation_state(conversation_id)

    # Check if this is a confirmation response
    if state.pending_confirmation:
        confirmation_type = classify_confirmation_response(user_message)

        if confirmation_type == CONFIRM:
            # Resume with confirmed tool, preserve message history
            return self._resume_with_confirmation(state, user_message)
        elif confirmation_type == DENY:
            # Clear pending, respond with cancellation
            return self._handle_denial(state, user_message)
        # else NEW_INTENT: fall through to normal processing

    # Normal flow: tool selection, execution, etc.
    ...
```

---

## Data Model Additions

### conversation_context
| Field | Type | Notes |
|-------|------|-------|
| conversation_id | UUID | PK/FK to agent_conversations |
| messages_json | JSONB | Recent message history |
| selected_tools | JSONB | Currently selected tool names |
| pending_confirmation | JSONB | Pending confirmation details (nullable) |
| summary | text | Rolling summary of dropped messages |
| message_count | int | Total messages in conversation |
| last_summarised_at | timestamptz | When summary was last updated |
| updated_at | timestamptz | |

---

## Behavioural Flow
1. Load existing summary and recent messages for conversation
2. Check if message count exceeds window size
3. If yes, summarise oldest messages and update summary
4. Build layered prompt with summary + recent messages
5. Execute agent run
6. Persist new messages
7. Update summary if needed post-run

---

## Summary Generation

Use Haiku to generate concise summaries:

```python
def summarise_messages(messages: list[Message], existing_summary: str | None) -> str:
    """Generate rolling summary of conversation context."""
    prompt = f"""
    Existing summary: {existing_summary or 'None'}

    New messages to incorporate:
    {format_messages(messages)}

    Generate a concise summary (max 300 tokens) that captures:
    - Key facts mentioned
    - User preferences expressed
    - Decisions made
    - Outstanding questions or tasks
    """
    # Call Haiku for cheap summarisation
```

---

## Guardrails
- Hard cap on message count (e.g., 50 messages max before forced summarisation)
- Max summary size (500 tokens)
- Fallback if prompt still exceeds threshold (truncate oldest summary content)

---

## Observability
- Log summary token size
- Log message window size
- Track summarisation frequency
- Alert if context approaches limits

---

## Success Metrics
- Conversations can exceed 50 messages without context overflow
- No degradation in agent reasoning quality
- Stable per-message token costs after window size reached

---

## Risks
- Poor summaries degrade conversational memory
- Summarisation latency on each message
- Loss of nuance in compressed context

---

## Implementation Milestones

### Phase 1: Stateful Conversations
1. Add `conversation_context` table and migration
2. Create `ConversationState` dataclass and persistence layer
3. Refactor `AgentRunner` to load/save conversation state
4. Remove `run_with_confirmation()` - replace with stateful `run()`

### Phase 2: Natural Language Confirmations
5. Implement `classify_confirmation_response()` using Haiku
6. Update run flow to detect and handle confirmation responses
7. Add confirmation detection tests

### Phase 3: Context Window Management
8. Implement message windowing logic (keep last N messages)
9. Implement summary generation with Haiku
10. Integrate summarisation into state management
11. Add context metrics logging

### Phase 4: Integration
12. Integrate with Telegram chat handler
13. End-to-end testing with long conversations
14. Performance validation (latency, cost)
