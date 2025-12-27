# Roadmap v2

Personal automation system for task management, newsletter processing, and AI-powered assistance via Telegram.

---

## In Progress

### PRD15: Newsletter Alert Service Refactor
**Goal**: Separate newsletter alerting from TelegramService for cleaner architecture.

- Move `send_unsent_newsletters()` to new `NewsletterAlertService` in `src/newsletters/`
- Extract message formatters to `src/newsletters/formatters.py`
- Simplify `TelegramService` to thin messaging wrapper
- Foundation for PRD04 (same pattern for reminders)

### PRD04: Daily Task & Goal Reminders
**Goal**: Scheduled Telegram notifications for tasks and goals.
**Depends on**: PRD15

- Daily task reminder (8am): overdue, due today, high priority this week
- Monthly goal review (1st of month): progress visualisation, at-risk detection
- Weekly reading list reminder (optional)
- Dagster scheduled jobs for orchestration

---

## Up Next

### PRD17: Tool Execution Timeout
**Priority**: Critical (AGENT-001)

Add configurable timeout to prevent agent hangs when tools block indefinitely.
- Wrap execution with `ThreadPoolExecutor`
- Default 30s timeout, configurable via `AgentConfig`
- Return actionable error to LLM on timeout

### PRD18: Bedrock toolUseId Validation
**Priority**: Critical (AGENT-002)

Validate Bedrock responses upfront instead of returning empty strings.
- Raise `BedrockResponseError` when required fields missing
- Clear error messages identifying problem field
- Prevents confusing downstream failures

---

## Backlog

### Features

#### PRD02: AI Article Summaries
Use Bedrock to generate ~100 char summaries for newsletter articles.
- Batch processing with Claude Haiku
- Cache summaries in database
- Fallback to truncation on failure

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
- Configurable feed management

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

#### URL to Reading List
Send URL via Telegram, AI extracts title/category and adds to reading list.

#### Recurring Tasks
Template-based recurring task creation (weekly reviews, monthly goals).

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
- Add better logging to the Notion API 

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
| TELE-006 | Rich message formatting (inline keyboards, code blocks) | Low      |
| TELE-008 | Message editing for progressive updates                 | Low      |

### Technical Debt

| ID     | Location            | Issue                                                        |
|--------|---------------------|--------------------------------------------------------------|
| TD-001 | telegram/client.py  | Remove environment variable fallback                         |
| TD-002 | telegram/service.py | Decouple from newsletter-specific logic (addressed by PRD15) |
| TD-003 | telegram/handler.py | Inject agent runner instead of lazy init                     |

---

## Future Ideas

| Idea                        | Description                                           |
|-----------------------------|-------------------------------------------------------|
| Async tool execution        | Convert tool handlers to async for parallel execution |
| Tool usage analytics        | Track tool success rates, latencies, usage patterns   |
| Smart reminders             | AI-powered prioritisation of what to highlight        |
| Snooze reminders            | Allow user to snooze via Telegram reply               |
| Voice message transcription | Transcribe voice messages before processing           |
| Progress trends             | Show goal progress trends over time                   |

---

## Completed

### PRDs

| PRD    | Description                                        | Date    |
|--------|----------------------------------------------------|---------|
| PRD01  | AI Agent Tool Registry                             | 2024-12 |
| PRD03  | Telegram Integration with Session Management       | 2024-12 |
| PRD081 | Prompt Caching                                     | 2024-12 |
| PRD082 | Context Management (sliding window, summarisation) | 2024-12 |
| PRD09  | Conversation Token & Cost Tracking                 | 2024-12 |
| PRD10  | Agent Internal Tool Selection                      | 2024-12 |
| PRD12  | Fuzzy Name Search                                  | 2024-12 |
| PRD13  | Notion Page Content Templates                      | 2024-12 |
| PRD14  | Agent Notion Descriptive Name Validation           | 2024-12 |
| PRD16  | Agent Config Centralisation                        | 2024-12 |
| PRD19  | CRUD Tool Factory                                  | 2024-12 |

### Agent Roadmap Items

| ID        | Description                                   | Date       |
|-----------|-----------------------------------------------|------------|
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
| Idea Tracking           | Full CRUD for ideas in Notion (query, get, create, update) |
| Message duplication fix | Fixed exponential message growth in conversation state     |

---

## Notes

- **Personal project**: No multi-user considerations needed
- **Hosting**: Currently local Docker setup, future AWS deployment
- **PRDs**: Detailed specs in `.claude/prds/`
