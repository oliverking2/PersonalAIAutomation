# PRD: GlitchTip Telegram Webhook

## Overview

Forward GlitchTip error alerts to Telegram for immediate visibility.

## Features

- **Webhook Endpoint**: FastAPI endpoint to receive GlitchTip webhook payloads
- **Error Formatting**: Format error details into readable Telegram message
- **Deduplication**: Avoid flooding Telegram with repeated errors (rate limiting)
- **Severity Filtering**: Only alert on errors above configurable severity threshold

## Implementation Notes

- Add endpoint at `/webhooks/glitchtip` in FastAPI
- Use existing `TelegramClient` for sending messages
- GlitchTip webhook format: https://glitchtip.com/documentation/webhooks
- Consider separate error chat ID from main bot chat

## Checklist

- [ ] FastAPI webhook endpoint for GlitchTip
- [ ] Telegram message formatting for errors
- [ ] Rate limiting/deduplication logic
- [ ] GlitchTip webhook configuration
- [ ] Tests for webhook handler
