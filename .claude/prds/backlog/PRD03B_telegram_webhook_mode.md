# PRD: Telegram Webhook Mode (Phase 2B)

## 1. Overview

### Purpose

Implement webhook-based Telegram transport as an alternative to the polling mode implemented in Phase 2A. This enables production deployment with lower latency and better resource efficiency.

### Prerequisites

This PRD assumes Phase 2A (Polling Mode) is complete, including:
- TelegramClient with `send_message()` and `get_updates()`
- MessageHandler for processing incoming messages
- SessionManager for session lifecycle
- Database tables for sessions, messages, and polling cursor

---

## 2. Goals & Non-Goals

### Goals

- Add webhook endpoint to FastAPI application
- Implement webhook secret validation
- Support switching between polling and webhook via configuration
- Document webhook registration process

### Non-Goals

- Automatic webhook registration (manual via Telegram API)
- SSL/TLS configuration (handled by infrastructure)
- Load balancing or horizontal scaling
- Changing any business logic (reuse Phase 2A components)

---

## 3. Architecture

### Webhook Flow

```
Telegram Server → HTTPS POST → FastAPI /telegram/webhook
    → MessageHandler (same as polling)
    → Response (200 OK immediate, async processing)
```

### Key Differences from Polling

| Aspect | Polling | Webhook |
|--------|---------|---------|
| Initiation | Bot polls Telegram | Telegram pushes to bot |
| Latency | Up to poll timeout | Near-instant |
| Resource usage | Continuous connections | On-demand |
| Infrastructure | No public endpoint | Public HTTPS required |
| Scaling | Single process | Stateless, scalable |

---

## 4. Implementation

### 4.1 FastAPI Webhook Endpoint

Location: `src/api/telegram/`

```python
@router.post("/webhook/{secret_token}")
async def telegram_webhook(
    secret_token: str,
    update: TelegramUpdate,
) -> dict[str, bool]:
    """Handle Telegram webhook updates."""
```

Features:
- Secret token in URL path for validation
- Immediate 200 OK response
- Background task for message processing
- Reuses existing MessageHandler

### 4.2 Configuration

New environment variables:
- `TELEGRAM_WEBHOOK_SECRET`: Random token for webhook URL security
- `TELEGRAM_WEBHOOK_BASE_URL`: Public base URL (e.g., `https://pa.oliverking.me.uk`)

Existing variable behaviour:
- `TELEGRAM_MODE=webhook`: Enables webhook mode (no polling runner needed)

### 4.3 Webhook Registration

Manual registration via Telegram API (documented in README):

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${TELEGRAM_WEBHOOK_BASE_URL}/telegram/webhook/${TELEGRAM_WEBHOOK_SECRET}"
```

Delete webhook (to switch back to polling):

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
```

---

## 5. Data Model

No new database tables required. Reuses:
- `telegram_sessions`
- `telegram_messages`
- `telegram_polling_cursor` (unused in webhook mode)

---

## 6. Functional Requirements

### FR1: Webhook Endpoint

- Accept POST requests with Telegram Update payload
- Validate secret token in URL path
- Return 200 OK immediately
- Process message asynchronously

### FR2: Error Handling

- Log errors but don't expose to Telegram
- Always return 200 OK (Telegram retries on non-2xx)
- Graceful handling of malformed payloads

### FR3: Configuration Switching

- `TELEGRAM_MODE=polling`: Run polling runner (Phase 2A)
- `TELEGRAM_MODE=webhook`: Register webhook endpoint, no polling

---

## 7. Non-Functional Requirements

- Response time: < 100ms for 200 OK
- Idempotent message handling (use update_id)
- Secure webhook URL (unguessable secret token)

---

## 8. Implementation Checklist

### Webhook Endpoint

- [ ] Create `src/api/telegram/` module with router
- [ ] Implement webhook endpoint with secret token validation
- [ ] Add background task for async message processing
- [ ] Register router in FastAPI app
- [ ] Add webhook-specific tests

### Configuration

- [ ] Add `TELEGRAM_WEBHOOK_SECRET` to config
- [ ] Add `TELEGRAM_WEBHOOK_BASE_URL` to config
- [ ] Update `.env_example` with new variables
- [ ] Conditional endpoint registration based on `TELEGRAM_MODE`

### Documentation

- [ ] Update README with webhook setup instructions
- [ ] Document webhook registration commands
- [ ] Document switching between modes

### Testing

- [ ] Unit tests for webhook endpoint
- [ ] Integration test with mock Telegram updates
- [ ] Verify secret token validation

---

## 9. Success Criteria

- Webhook endpoint accepts and processes Telegram updates
- Invalid secret tokens are rejected
- Message handling identical to polling mode
- Mode switching via configuration only
- No changes to MessageHandler or SessionManager
