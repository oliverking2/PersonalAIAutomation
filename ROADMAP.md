# Roadmap

Personal automation system for task management, newsletter processing, and AI-powered assistance via Telegram.

---

## Up Next

---

## Backlog

#### PRD11: Agent Integration Testing
End-to-end conversation flow testing.
- Multi-turn scenarios (clarification, confirmation, denial)
- Mock infrastructure for deterministic tests
- Conversation simulator helper

### Telegram Improvements

| ID       | Description                                                                                                           | Priority |
|----------|-----------------------------------------------------------------------------------------------------------------------|----------|
| TELE-010 | Migrate alert formatters to Markdown/MarkdownV2                                                                       | Medium   |
| TELE-005 | Structured logging with chat_id, session_id <br/>(partial: some context in logs, needs systematic use of contextvars) | Medium   |
| TELE-009 | Integration test suite                                                                                                | Medium   |

### Technical Debt

| ID     | Location            | Issue                                                                                                             |
|--------|---------------------|-------------------------------------------------------------------------------------------------------------------|
| TD-003 | telegram/handler.py | Inject agent runner instead of lazy init (partial: accepts injection but falls back to lazy init if not provided) |

---

## Future Ideas

| Idea                        | Description                                              |
|-----------------------------|----------------------------------------------------------|
| Tool usage analytics        | Track tool success rates, latencies, usage patterns      |
| Smart reminders             | AI-powered prioritisation of what to highlight           |
| Running Integration         | Integrate with Strava/Garmin to track running activities |
| CI/CD Integration           | Integrate with GitHub Actions for CI/CD pipelines        |
