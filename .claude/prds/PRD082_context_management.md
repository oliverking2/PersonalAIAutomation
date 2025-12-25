# PRD 082: Context Window Management

## Overview
Manage conversational context to prevent context window exhaustion in long-running conversations by implementing sliding windows and rolling summaries.

---

## Problem Statement
In multi-turn conversations (especially via Telegram), the agent will accumulate messages leading to:
- Linear token growth per message
- Eventual context window exhaustion
- Increasing cost per message

---

## Goals
- Cap context growth deterministically
- Preserve reasoning quality across long conversations
- Support long-running Telegram conversations

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

## Data Model Additions

### conversation_context
| Field | Type | Notes |
|-------|------|-------|
| conversation_id | UUID | PK/FK to agent_conversations |
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
1. Add conversation_context table and migration
2. Implement message windowing logic
3. Implement summary generation with Haiku
4. Integrate with AgentRunner
5. Add context metrics logging
6. Test with long Telegram conversations
