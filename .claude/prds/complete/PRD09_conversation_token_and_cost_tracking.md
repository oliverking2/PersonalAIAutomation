# PRD09: Conversation, Token, and Cost Tracking

## Overview
This PRD defines the implementation of durable conversation persistence, Bedrock token usage tracking, and cost attribution for the personal AI assistant.

The goal is to introduce **observability and cost transparency** without changing agent behaviour.

---

## Problem Statement
The current agent runtime executes multi-step Bedrock reasoning loops without persistent tracking of:
- token usage per Bedrock call
- total cost per agent run or conversation
- historical conversation state
- request/response content for debugging

This limits cost control, debugging, and future optimisation.

---

## Goals
- Persist conversations, agent runs, and LLM calls in PostgreSQL
- Track input/output/cache tokens and estimated cost
- Store request messages and response content for debugging
- Enable aggregation at run and conversation level
- Maintain zero behavioural change to agent output

---

## Non-Goals
- Prompt optimisation or truncation
- User-facing cost dashboards
- Bedrock Agents migration
- Telegram session management (separate PRD03)

---

## Architecture Fit
- Ingress: Telegram, FastAPI, Dagster
- AI Layer: AgentRunner + Bedrock Converse
- Persistence: PostgreSQL via SQLAlchemy
- Tracking: Context variable pattern for non-invasive instrumentation

---

## Data Model

### conversations
| Field                    | Type          | Notes                                           |
|--------------------------|---------------|-------------------------------------------------|
| id                       | UUID          | PK                                              |
| external_id              | text          | Optional external identifier (nullable, unique) |
| started_at               | timestamptz   | When conversation started                       |
| ended_at                 | timestamptz   | When conversation ended (nullable)              |
| total_input_tokens       | int           | Aggregated from all runs                        |
| total_output_tokens      | int           | Aggregated from all runs                        |
| total_cache_read_tokens  | int           | Aggregated from all runs                        |
| total_estimated_cost_usd | numeric(10,6) | Aggregated from all runs                        |
| created_at               | timestamptz   | Record creation time                            |

### agent_runs
| Field                    | Type          | Notes                                       |
|--------------------------|---------------|---------------------------------------------|
| id                       | UUID          | PK                                          |
| conversation_id          | UUID          | FK to conversations                         |
| user_message             | text          | Raw user input                              |
| final_response           | text          | Agent's final response (nullable)           |
| stop_reason              | text          | end_turn, confirmation_required, error, etc |
| steps_taken              | int           | Number of tool execution steps              |
| started_at               | timestamptz   | When run started                            |
| ended_at                 | timestamptz   | When run completed (nullable)               |
| total_input_tokens       | int           | Aggregated from all calls                   |
| total_output_tokens      | int           | Aggregated from all calls                   |
| total_cache_read_tokens  | int           | Aggregated from all calls                   |
| total_estimated_cost_usd | numeric(10,6) | Aggregated from all calls                   |

### llm_calls
| Field              | Type          | Notes                               |
|--------------------|---------------|-------------------------------------|
| id                 | UUID          | PK                                  |
| agent_run_id       | UUID          | FK to agent_runs                    |
| model_alias        | text          | haiku, sonnet, opus                 |
| model_id           | text          | Full Bedrock model ID               |
| call_type          | text          | chat, selector                      |
| request_messages   | jsonb         | Messages sent to Bedrock            |
| response_content   | jsonb         | Response content from Bedrock       |
| input_tokens       | int           | From usage.inputTokens              |
| output_tokens      | int           | From usage.outputTokens             |
| cache_read_tokens  | int           | From usage.cacheReadInputTokenCount |
| estimated_cost_usd | numeric(10,6) | Calculated from pricing             |
| latency_ms         | int           | Call duration (nullable)            |
| called_at          | timestamptz   | When call was made                  |

---

## Instrumentation Approach

### Context Variable Pattern
Use Python's `contextvars.ContextVar` to hold tracking context:

1. Create `TrackingContext` with run_id, conversation_id, and llm_calls list
2. Set context before AgentRunner.run()
3. BedrockClient.converse() records calls when context is active
4. Clear context after run completes (in finally block)

This approach:
- Captures all LLM calls (chat + selector) in one place
- Is non-invasive (tracking is opt-in)
- Is thread-safe via ContextVar
- Doesn't change existing method signatures

---

## Cost Calculation

### Static Pricing Table (per 1,000 tokens)
| Model   | Input  | Output | Cache Read  |
|---------|--------|--------|-------------|
| haiku   | $0.001 | $0.005 | $0.0001     |
| sonnet  | $0.003 | $0.015 | $0.0003     |
| opus    | $0.005 | $0.025 | $0.0005     |

### Calculation Formula
```
cost = (input_tokens / 1000 * input_rate)
     + (output_tokens / 1000 * output_rate)
     + (cache_read_tokens / 1000 * cache_read_rate)
```

Pricing stored in `src/agent/pricing.py` for easy updates.

---

## Behavioural Flow
1. Create conversation (or reuse existing)
2. Create agent_run with user_message
3. Set tracking context
4. Run agent (BedrockClient.converse() records each call)
5. On completion:
   - Complete agent_run with totals
   - Persist all llm_calls
   - Update conversation totals
6. Clear tracking context

---

## Logging
INFO on run completion:
```
Agent run completed: id=..., tokens=1234/567, cost=$0.012345
```

DEBUG on each LLM call:
```
Recorded LLM call: model=sonnet, tokens=1000/200, cost=$0.006000
```

---

## File Structure

### New Files
```
src/agent/
    pricing.py           # MODEL_PRICING and calculate_cost()
    tracking.py          # TrackingContext, LLMCallRecord, contextvars

src/database/agent_tracking/
    __init__.py          # Public exports
    models.py            # Conversation, AgentRun, LLMCall ORM models
    operations.py        # Database operations

testing/agent/
    test_pricing.py
    test_tracking.py

testing/database/agent_tracking/
    __init__.py
    test_operations.py
```

### Modified Files
- `src/agent/client.py` - Record calls when tracking context active
- `src/agent/runner.py` - Accept and manage tracking_context
- `src/agent/selector.py` - Pass call_type="selector"
- `alembic/env.py` - Import new models

---

## Success Metrics
- 100% Bedrock calls recorded when tracking enabled
- Accurate per-run and per-conversation totals
- No agent behaviour regression
- Request/response content available for debugging

---

## Risks
| Risk | Mitigation |
|------|------------|
| Large JSON payloads | PostgreSQL JSONB compression; consider retention policy |
| Pricing drift | Single file for pricing; easy to update |
| Performance overhead | Minimal - only DB writes, no blocking |
| Context threading issues | ContextVar is thread-safe |

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `src/agent/pricing.py` with MODEL_PRICING and calculate_cost()
- [ ] Create `src/agent/tracking.py` with TrackingContext and LLMCallRecord
- [ ] Write tests for pricing calculations

### Phase 2: Database Layer
- [ ] Create `src/database/agent_tracking/models.py`
- [ ] Create `src/database/agent_tracking/operations.py`
- [ ] Create `src/database/agent_tracking/__init__.py`
- [ ] Create Alembic migration
- [ ] Write database operation tests

### Phase 3: Instrumentation
- [ ] Modify BedrockClient.converse() to record calls
- [ ] Modify ToolSelector.select() to pass call_type
- [ ] Write tracking tests

### Phase 4: Integration
- [ ] Modify AgentRunner to accept tracking_context
- [ ] Modify AgentRunner.run() to set/clear context
- [ ] Write integration tests

### Phase 5: Validation
- [ ] Run `make check`
- [ ] Update README.md
