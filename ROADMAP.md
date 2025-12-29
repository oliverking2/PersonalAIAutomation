# Roadmap v2

Personal automation system for task management, newsletter processing, and AI-powered assistance via Telegram.

---

## Up Next

#### PRD05: Substack & Medium Integration
Extend newsletter extraction to more sources.
- Substack parser (multiple feeds: Joe Reis, DataExpert.io, etc.)
  - Joe Reis
  - DataExpert.io (Subscription needed?)
  - Daily Dose of Data Science
  - Seattle Data Guy
  - https://practicaldatamodeling.substack.com
  - more feeds added recently
- Medium Daily Digest parser (requires auth handling)

---

## Backlog

### Features

#### PRD03B: Telegram Webhook Mode
Production deployment with webhook instead of polling.
- FastAPI endpoint with secret token validation
- Lower latency, better resource efficiency
- Mode switching via `TELEGRAM_MODE` config

#### PRD07: GlitchTip Telegram Webhook
Forward error alerts to Telegram.
- Webhook endpoint at `/webhooks/glitchtip`
- Error formatting and rate limiting
- Severity filtering

### Infrastructure

#### PRD06: CI/CD Pipeline
GitHub Actions for automated testing and deployment.
- Run `make check` on PR and push to main
- Docker image builds on main merge
- Deployment on release tags

#### PRD11: Agent Integration Testing
End-to-end conversation flow testing.
- Multi-turn scenarios (clarification, confirmation, denial)
- Mock infrastructure for deterministic tests
- Conversation simulator helper

### Misc Improvements
(No items currently)

### Agent Improvements

| ID        | Description                                               | Priority |
|-----------|-----------------------------------------------------------|----------|
| AGENT-006 | Prevent LLM from repeatedly requesting unknown tools      | High     |
| AGENT-007 | Replace `list[Any]` with `MessageTypeDef` in runner state | Medium   |
| AGENT-009 | Remove synthetic "I understand" message from context      | Medium   |
| AGENT-013 | Validate `tool_names` is a list in selector response      | Medium   |
| AGENT-015 | Standardise error return formats in tools                 | Low      |
| AGENT-017 | Add request ID propagation to API client                  | Low      |
| AGENT-020 | Improve BedrockClient error context                       | Low      |

### Telegram Improvements

| ID       | Description                                             | Priority |
|----------|---------------------------------------------------------|----------|
| TELE-005 | Structured logging with chat_id, session_id             | Medium   |
| TELE-003 | Graceful long-poll timeout handling                     | Medium   |
| TELE-009 | Integration test suite                                  | Medium   |
| TELE-004 | Connection pooling with requests.Session                | Low      |

### Technical Debt

| ID     | Location            | Issue                                    |
|--------|---------------------|------------------------------------------|
| TD-001 | telegram/client.py  | Remove environment variable fallback     |
| TD-003 | telegram/handler.py | Inject agent runner instead of lazy init |

---

## Future Ideas

| Idea                        | Description                                              |
|-----------------------------|----------------------------------------------------------|
| Async tool execution        | Convert tool handlers to async for parallel execution    |
| Tool usage analytics        | Track tool success rates, latencies, usage patterns      |
| Smart reminders             | AI-powered prioritisation of what to highlight           |
| Running Integration         | Integrate with Strava/Garmin to track running activities |
---

## Completed

### PRDs

| PRD    | Description                                        | Date       |
|--------|----------------------------------------------------|------------|
| PRD18  | Bedrock toolUseId Validation                       | 2025-12-28 |
| PRD22  | API Logging Improvements                           | 2024-12-28 |
| PRD17  | Tool Execution Timeout                             | 2024-12-28 |
| PRD01  | AI Agent Tool Registry                             | 2024-12    |
| PRD03  | Telegram Integration with Session Management       | 2024-12    |
| PRD081 | Prompt Caching                                     | 2024-12    |
| PRD082 | Context Management (sliding window, summarisation) | 2024-12    |
| PRD09  | Conversation Token & Cost Tracking                 | 2024-12    |
| PRD10  | Agent Internal Tool Selection                      | 2024-12    |
| PRD12  | Fuzzy Name Search                                  | 2024-12    |
| PRD13  | Notion Page Content Templates                      | 2024-12    |
| PRD14  | Agent Notion Descriptive Name Validation           | 2024-12    |
| PRD16  | Agent Config Centralisation                        | 2024-12    |
| PRD19  | CRUD Tool Factory                                  | 2024-12    |
| PRD20  | Unified Alert System (supersedes PRD04 & PRD15)    | 2024-12    |

### Agent Roadmap Items

| ID        | Description                                   | Date       |
|-----------|-----------------------------------------------|------------|
| AGENT-002 | Bedrock toolUseId validation (via PRD18)      | 2025-12-28 |
| AGENT-001 | Tool execution timeout (via PRD17)            | 2024-12-28 |
| AGENT-003 | CRUD tool factory (via PRD19)                 | 2024-12    |
| AGENT-008 | Validate classification response with retries | 2024-12-25 |
| AGENT-012 | Tool re-selection on each turn                | 2024-12-25 |
| AGENT-016 | Centralise configuration (via PRD16)          | 2024-12    |
| AGENT-021 | Remove unused session parameter               | 2024-12-25 |
| AGENT-022 | BedrockClient helper methods                  | 2024-12-25 |
| AGENT-023 | Refactor AgentRunner helpers                  | 2024-12-25 |
| AGENT-024 | Remove unused confirmation parameters         | 2024-12-25 |
| AGENT-025 | Fix HITL confirmation flow                    | 2024-12-25 |
| AGENT-026 | Add today's date to system prompt             | 2024-12-25 |
| AGENT-027 | Include confirmation message in conversation  | 2024-12-25 |
| AGENT-028 | Handle multiple tool uses in response         | 2024-12-25 |
| AGENT-029 | Context-aware additive tool selection         | 2024-12-25 |
| AGENT-030 | Execute ALL tools in multi-tool response      | 2024-12-26 |
| AGENT-031 | Fuzzy name search for query tools             | 2024-12-26 |
| AGENT-F06 | Descriptive name validation (via PRD14)       | 2024-12    |

### Telegram Roadmap Items

| ID       | Description                             | Date       |
|----------|-----------------------------------------|------------|
| TELE-007 | Typing indicators while agent processes | 2024-12-27 |

### Other

| Item                    | Description                                                |
|-------------------------|------------------------------------------------------------|
| Alert ops error notify  | Send errors to Errors bot instead of silently failing      |
| API config standardise  | Use API_HOST and API_PORT consistently across codebase     |
| Batch HITL confirmation | Multi-tool confirmation with partial approvals/corrections |
| Idea Tracking           | Full CRUD for ideas in Notion (query, get, create, update) |
| Message duplication fix | Fixed exponential message growth in conversation state     |

---

## Notes

- **Personal project**: No multi-user considerations needed
- **Hosting**: Currently local Docker setup, future AWS deployment
- **PRDs**: Detailed specs in `.claude/prds/`
