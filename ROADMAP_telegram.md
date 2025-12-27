# Telegram Module Roadmap

This document provides a review of the current Telegram module implementation and outlines planned improvements and future work.

## Current State

The Telegram module (`src/telegram/`) provides two main capabilities:
1. **Newsletter Alerts** (Phase 1): One-way message sending for newsletter notifications
2. **Two-Way Chat** (Phase 2A): Bidirectional chat with session management and AI agent integration

### Architecture Overview

```
src/telegram/
├── __init__.py           # Module exports
├── client.py             # TelegramClient - low-level API wrapper
├── config.py             # TelegramSettings with pydantic-settings
├── handler.py            # MessageHandler - orchestrates message processing
├── models.py             # Pydantic models for Telegram data
├── polling.py            # PollingRunner - long-polling loop
├── service.py            # TelegramService - newsletter alerts
├── session_manager.py    # SessionManager - session lifecycle
└── utils.py              # Utility functions
```

### Configuration

The module uses `pydantic-settings` for configuration with environment variables:

| Variable                           | Required | Default   | Description                             |
|------------------------------------|----------|-----------|-----------------------------------------|
| `TELEGRAM_BOT_TOKEN`               | Yes      | -         | Bot token from @BotFather               |
| `TELEGRAM_ALLOWED_CHAT_IDS`        | Yes      | -         | Comma-separated allowed chat IDs        |
| `TELEGRAM_CHAT_ID`                 | No       | -         | Default chat for newsletter alerts      |
| `TELEGRAM_MODE`                    | No       | `polling` | Transport mode (polling/webhook)        |
| `TELEGRAM_POLL_TIMEOUT`            | No       | `30`      | Long polling timeout (1-60 seconds)     |
| `TELEGRAM_SESSION_TIMEOUT_MINUTES` | No       | `10`      | Session inactivity timeout (1-60 min)   |
| `TELEGRAM_ERROR_RETRY_DELAY`       | No       | `5`       | Delay between retries after error (1-60s) |
| `TELEGRAM_MAX_CONSECUTIVE_ERRORS`  | No       | `5`       | Max errors before backing off (1-20)    |
| `TELEGRAM_BACKOFF_DELAY`           | No       | `30`      | Backoff delay after max errors (5-300s) |

## Completed Work

### Phase 1: Newsletter Alerts
- [x] `TelegramClient` for sending messages
- [x] `TelegramService` for newsletter alert workflow
- [x] HTML message formatting with article links
- [x] Error handling and retry logic

### Phase 2A: Two-Way Chat (Polling Mode)
- [x] Long polling with `PollingRunner`
- [x] Session management with timeout-based expiration
- [x] Message handler with AI agent integration
- [x] Database models for sessions and messages
- [x] `/newchat` command for session reset
- [x] Chat ID allowlist enforcement

### Configuration Improvements (Recent)
- [x] Migrated to `pydantic-settings` for configuration
- [x] Made `allowed_chat_ids` required for security
- [x] Added validation constraints for timeout values
- [x] Removed redundant `DEFAULT_POLL_TIMEOUT` constant

---

## Planned Improvements

### Security Enhancements

#### TELE-001: Rate Limiting
**Priority**: High
**Complexity**: Medium

Add rate limiting to prevent abuse:
- Per-chat message rate limits (e.g., 10 messages/minute)
- Global bot rate limits aligned with Telegram's limits
- Graceful degradation with informative error messages

```python
# Proposed configuration
rate_limit_per_chat: int = Field(default=10, description="Max messages per minute per chat")
rate_limit_window_seconds: int = Field(default=60)
```

#### TELE-002: Message Content Validation
**Priority**: Medium
**Complexity**: Low

Add input validation before passing to agent:
- Maximum message length validation
- Strip potentially harmful content
- Sanitise for logging (no PII)

### Reliability Improvements

#### TELE-003: Graceful Long-Poll Timeout Handling
**Priority**: Medium
**Complexity**: Low

Currently, timeouts during long polling raise `TelegramClientError`. Consider:
- Return empty list instead of raising for expected timeouts
- Only raise for unexpected connection failures
- Distinguish between expected vs unexpected timeouts

#### TELE-004: Connection Pooling
**Priority**: Low
**Complexity**: Medium

Use `requests.Session` for connection pooling:
- Reuse TCP connections for better performance
- Configure connection pool size
- Add keep-alive support

#### TELE-005: Structured Logging
**Priority**: Medium
**Complexity**: Low

Enhance logging with structured context:
- Add `chat_id`, `session_id`, `update_id` to all log entries
- Use correlation IDs for request tracing
- Add timing metrics for agent invocations

### Feature Improvements

#### TELE-006: Rich Message Formatting
**Priority**: Low
**Complexity**: Medium

Enhance agent response formatting:
- Support for inline keyboards for confirmations
- Markdown or HTML formatting based on response type
- Code block formatting for technical responses

#### TELE-007: Typing Indicators
**Priority**: Low
**Complexity**: Low

Show "typing" indicator while agent processes:
- Send `sendChatAction` with "typing" before agent invocation
- Provides better user experience for longer operations

#### TELE-008: Message Editing Support
**Priority**: Low
**Complexity**: Medium

Support editing previously sent messages:
- Track sent message IDs per session
- Allow agent to update responses
- Useful for progressive updates on long operations

### Testing Improvements

#### TELE-009: Integration Test Suite
**Priority**: Medium
**Complexity**: High

Add integration tests with mocked Telegram API:
- End-to-end flow testing (poll → handle → respond)
- Session lifecycle testing
- Error recovery scenarios

#### TELE-010: Load Testing
**Priority**: Low
**Complexity**: Medium

Add performance benchmarks:
- Multiple concurrent chat sessions
- High message throughput
- Memory usage under load

---

## Future Phases

### Phase 2B: Webhook Mode
**Reference**: PRD03B_telegram_webhook_mode.md

Implement webhook-based message receiving:
- FastAPI endpoints for webhook callbacks
- Webhook registration and management
- Signature verification for security
- Automatic fallback to polling

### Phase 3: Media Support
Support for rich media messages:
- Photo and document receiving
- Voice message transcription
- Image generation responses

### Phase 4: Multi-User Support
Enterprise features:
- User-specific agent configurations
- Per-user conversation history
- Role-based access control

---

## Technical Debt

### TD-001: Client Environment Variable Fallback
**Location**: `src/telegram/client.py:44-45`

The `TelegramClient` still reads directly from environment variables as a fallback. Consider:
- Requiring explicit parameters (breaking change)
- Using `TelegramSettings` internally for consistency
- Deprecating environment variable fallback

### TD-002: Service Module Coupling
**Location**: `src/telegram/service.py`

The `TelegramService` is tightly coupled to newsletter alerting. Consider:
- Extracting message formatting to a separate module
- Making it more generic for other alert types
- Separating "send" operations from "newsletter" operations

### TD-003: Handler Agent Runner Lazy Initialisation
**Location**: `src/telegram/handler.py:68-79`

The agent runner is lazily created in `_get_agent_runner()`. Consider:
- Injecting as required dependency
- Factory pattern for cleaner testing
- Configuration-driven agent selection

---

## Dependencies

The Telegram module has dependencies on:
- `src/database/telegram/` - Session and message persistence
- `src/database/agent_tracking/` - Agent conversation tracking
- `src/agent/` - AI agent execution

Future work should consider the impact on these dependencies.

---

## Review Notes

### Strengths
1. Clean separation between client, handler, and session management
2. Good use of Pydantic for configuration and data models
3. Comprehensive test coverage
4. Proper error handling with specific exception types
5. Security-conscious design with required allowlist

### Areas for Improvement
1. Consider async/await for I/O operations
2. Add request/response correlation for debugging
3. Consider webhook mode for lower latency
4. Add observability hooks (metrics, tracing)
