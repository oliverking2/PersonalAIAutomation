# PRD: GlitchTip Telegram Webhook

## Overview

Forward GlitchTip error alerts to Telegram for immediate visibility when production errors occur.

## Features

- **Webhook Endpoint**: FastAPI endpoint to receive GlitchTip webhook payloads
- **Error Formatting**: Format error details into readable Telegram message with title, URL, and context
- **Webhook Authentication**: Separate webhook secret (not the main API token)
- **Test Endpoint**: Trigger a test error to verify the integration

## Technical Details

### GlitchTip Webhook Format

GlitchTip sends Slack-compatible webhook payloads:

```json
{
  "alias": "optional-alias",
  "text": "Alert text",
  "attachments": [
    {
      "title": "Error Title",
      "title_link": "https://glitchtip.example.com/project/issues/123",
      "text": "Error message or stack trace preview",
      "color": "#ff0000",
      "fields": [
        {"title": "project", "value": "my-project", "short": true},
        {"title": "environment", "value": "production", "short": true},
        {"title": "release", "value": "v1.2.3", "short": true}
      ]
    }
  ]
}
```

### Module Structure

```
src/api/webhooks/
├── __init__.py
├── router.py              # Combines webhook sub-routers
└── glitchtip/
    ├── __init__.py
    ├── endpoints.py       # POST /webhooks/glitchtip, POST /webhooks/glitchtip/test
    ├── models.py          # GlitchTipAlert, Attachment, Field
    └── formatter.py       # Format payload to Telegram HTML
```

### Configuration

| Environment Variable       | Description                             | Default                        |
|----------------------------|-----------------------------------------|--------------------------------|
| `GLITCHTIP_WEBHOOK_SECRET` | Secret token for webhook authentication | Required                       |
| `TELEGRAM_ERROR_CHAT_ID`   | Telegram chat ID for error alerts       | Required (already exists)      |

### Authentication

The webhook uses a separate secret from the main API:
- GlitchTip sends the secret in the URL: `/webhooks/glitchtip?token=<secret>`
- This keeps webhook auth separate from the main Bearer token flow
- Validates against `GLITCHTIP_WEBHOOK_SECRET` environment variable

### Endpoints

#### `POST /webhooks/glitchtip?token=<secret>`
Receives GlitchTip webhook payloads and forwards to Telegram.

#### `POST /webhooks/glitchtip/test?token=<secret>`
Triggers a test error alert to verify the integration is working. Sends a sample alert to Telegram without requiring a real GlitchTip event.

### Telegram Message Format

```
🚨 <b>Error Alert</b>

<b>{title}</b>
{text preview}

📦 Project: {project}
🌍 Environment: {environment}
🏷️ Release: {release}

🔗 <a href="{title_link}">View in GlitchTip</a>
```

## Implementation Notes

- Add new router at `/webhooks` prefix (no auth dependency on router level)
- Individual webhook endpoints handle their own authentication via query param
- Use existing `TelegramClient.send_message_sync()` for sending
- Use existing `TELEGRAM_ERROR_CHAT_ID` environment variable
- No deduplication needed - GlitchTip handles alert rules and rate limiting

## Checklist

- [ ] Create `src/api/webhooks/` module structure
- [ ] Pydantic models for GlitchTip payload (Field, Attachment, GlitchTipAlert)
- [ ] Webhook endpoint with token query param authentication
- [ ] Test endpoint to trigger sample error alert
- [ ] Telegram HTML formatter for error alerts
- [ ] Register webhooks router in `src/api/app.py`
- [ ] Unit tests for models and formatter
- [ ] Integration test for webhook endpoint
- [ ] Update `.env_example` with `GLITCHTIP_WEBHOOK_SECRET`
