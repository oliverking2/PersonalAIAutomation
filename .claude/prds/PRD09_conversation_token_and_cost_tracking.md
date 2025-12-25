# PRD 01: Conversation, Token, and Cost Tracking

## Overview
This PRD defines the implementation of durable conversation persistence, Bedrock token usage tracking, and cost attribution for the personal AI assistant.

The goal is to introduce **observability and cost transparency** without changing agent behaviour.

---

## Problem Statement
The current agent runtime executes multi-step Bedrock reasoning loops without persistent tracking of:
- token usage per Bedrock call
- total cost per agent run or conversation
- historical conversation state

This limits cost control, debugging, and future optimisation.

---

## Goals
- Persist conversations, agent runs, and LLM calls in PostgreSQL
- Track input/output/cache tokens and estimated cost
- Enable aggregation at run and conversation level
- Maintain zero behavioural change to agent output

---

## Non-Goals
- Prompt optimisation or truncation
- User-facing cost dashboards
- Bedrock Agents migration

---

## Architecture Fit
- Ingress: Telegram, FastAPI, Dagster
- AI Layer: AgentRunner + Bedrock Converse
- Persistence: PostgreSQL via SQLAlchemy

---

## Data Model

### conversations
| Field | Type | Notes |
|-----|-----|------|
| id | UUID | PK |
| ingress_type | enum | telegram, api, schedule |
| external_id | text | telegram chat id etc |
| created_at | timestamptz | |
| last_active_at | timestamptz | |

### agent_runs
| Field | Type | Notes |
|-----|-----|------|
| id | UUID | PK |
| conversation_id | UUID | FK |
| user_message | text | raw input |
| started_at | timestamptz | |
| completed_at | timestamptz | |
| steps | int | |
| status | enum | success, error, fallback |

### llm_calls
| Field | Type | Notes |
|-----|-----|------|
| id | UUID | PK |
| agent_run_id | UUID | FK |
| model_id | text | |
| input_tokens | int | |
| output_tokens | int | |
| total_tokens | int | |
| cache_read_tokens | int | |
| cache_write_tokens | int | |
| latency_ms | int | |
| estimated_cost_usd | numeric | derived |
| created_at | timestamptz | |

---

## Behavioural Flow
1. Resolve or create conversation on ingress
2. Start agent_run
3. For each Bedrock call:
   - capture usage
   - persist llm_calls record
4. Aggregate totals on completion

---

## Cost Calculation
- Static pricing table per model
- Derived fields stored in DB
- No runtime dependency on AWS pricing APIs

---

## Logging
INFO on run completion:
```
Agent run completed: run_id=..., tokens_in=..., tokens_out=..., cost_usd=...
```

---

## Success Metrics
- 100 percent Bedrock calls recorded
- Accurate per-run and per-conversation totals
- No agent behaviour regression

---

## Risks
- Slight increase in DB writes
- Pricing config drift

---

## Implementation Milestones
1. DB schema + migrations
2. SQLAlchemy models
3. Bedrock client instrumentation
4. AgentRunner integration
5. End-to-end validation
