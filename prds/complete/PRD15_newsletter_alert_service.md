# PRD15: Newsletter Alert Service Refactor

**Status: SUPERSEDED by PRD20**
**Updated: 2024-12-27**

## Overview

Move newsletter alerting logic from `src/telegram/service.py` to a dedicated `NewsletterAlertService` in the newsletters module. This improves separation of concerns by keeping newsletter logic in the newsletters module and removes the misleadingly-named `TelegramService`.

## Problem Statement

The current `TelegramService` in `src/telegram/service.py`:

1. **Misleading name**: It only handles newsletter alerts, not generic Telegram messaging
2. **Wrong location**: Newsletter-specific logic lives in the telegram module instead of newsletters
3. **Redundant abstraction**: `TelegramClient` already provides generic `send_message()` - no wrapper needed
4. **Mixed concerns**: Combines message formatting, sending, and database operations

The telegram module has grown significantly (handler, polling, chat integration) while `TelegramService` remains a newsletter-specific outlier that should live elsewhere.

## Current Architecture

```
src/telegram/
├── client.py       # Generic Telegram API client (send_message, get_updates, send_chat_action)
├── handler.py      # Chat message handling with agent integration
├── polling.py      # Long-polling runner
├── service.py      # ← Newsletter-specific, misleadingly named "TelegramService"
└── ...
```

```python
# src/telegram/service.py (current - misleading location)
class TelegramService:
    def __init__(self, session: Session, client: TelegramClient) -> None:
        self._session = session
        self._client = client

    def send_unsent_newsletters(self) -> SendResult:
        """Newsletter-specific logic that shouldn't be in telegram module."""
        ...

    def _format_newsletter_message(self, newsletter: Newsletter) -> str:
        """Formatting logic that belongs in newsletters module."""
        ...
```

## Proposed Architecture

```
src/newsletters/
├── alert_service.py    # NEW: NewsletterAlertService
├── formatters.py       # NEW: Newsletter message formatting
└── tldr/               # (existing)

src/telegram/
├── client.py           # TelegramClient (unchanged - already has send_message)
├── handler.py          # Chat handling (unchanged)
├── polling.py          # Polling runner (unchanged)
└── service.py          # DELETED - no longer needed
```

```
┌───────────────────────────────────────────────────────────────────────┐
│                     NewsletterAlertService                            │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ send_unsent_newsletters()                                        ││
│  └──────────────────────────────────────────────────────────────────┘│
│              ↓                              ↓                         │
│       TelegramClient                   Session (DB)                   │
│       (direct usage)                                                  │
└───────────────────────────────────────────────────────────────────────┘
```

## Implementation

### New Files

```
src/newsletters/
├── __init__.py          # Update exports
├── alert_service.py     # NEW: NewsletterAlertService
├── formatters.py        # NEW: Newsletter message formatting
└── tldr/                # (existing)
```

### NewsletterAlertService

```python
# src/newsletters/alert_service.py

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.database.newsletters import Newsletter, get_unsent_newsletters, mark_newsletter_alerted
from src.newsletters.formatters import format_newsletter_message
from src.telegram.client import TelegramClient, TelegramClientError

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """Result of sending newsletter alerts."""

    newsletters_sent: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def newsletters_failed(self) -> int:
        """Count of failed newsletters."""
        return len(self.errors)


class NewsletterAlertService:
    """Service for sending newsletter alerts via Telegram.

    Handles querying unsent newsletters, formatting messages,
    sending via Telegram, and tracking sent state.
    """

    def __init__(
        self,
        session: Session,
        client: TelegramClient,
    ) -> None:
        """Initialise the newsletter alert service.

        :param session: Database session for newsletter operations.
        :param client: Telegram client for sending messages.
        """
        self._session = session
        self._client = client

    def send_unsent_newsletters(self) -> SendResult:
        """Query and send all unsent newsletters.

        Fetches newsletters that haven't been sent yet, formats them
        for Telegram, sends them, and marks them as sent.

        :returns: Result with count of sent/failed newsletters.
        """
        result = SendResult()
        unsent = get_unsent_newsletters(self._session)

        logger.info(f"Found {len(unsent)} newsletters to alert")

        for newsletter in unsent:
            try:
                self._send_newsletter_alert(newsletter)
                result.newsletters_sent += 1
            except TelegramClientError as e:
                error_msg = f"Failed to send alert for newsletter {newsletter.id}: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)

        logger.info(
            f"Notification sending complete: {result.newsletters_sent} sent, "
            f"{result.newsletters_failed} errors"
        )

        return result

    def _send_newsletter_alert(self, newsletter: Newsletter) -> None:
        """Send a Telegram alert for a single newsletter.

        :param newsletter: The newsletter to send an alert for.
        :raises TelegramClientError: If sending the message fails.
        """
        message = format_newsletter_message(newsletter)
        self._client.send_message(message)
        mark_newsletter_alerted(self._session, newsletter.id)
```

### Newsletter Formatters

```python
# src/newsletters/formatters.py

from urllib.parse import urlparse

from src.database.newsletters import Article, Newsletter


def format_newsletter_message(newsletter: Newsletter) -> str:
    """Format a newsletter for Telegram display.

    :param newsletter: Newsletter with articles to format.
    :returns: HTML-formatted message string.
    """
    lines = [f"<b>{newsletter.newsletter_type.value} - {newsletter.subject}</b>", ""]

    for article in newsletter.articles:
        lines.append(f"<b>{article.title}</b>")
        if article.description:
            lines.append(f"{article.description[:150]}")
        lines.append(format_article_link(article))
        lines.append("")

    return "\n".join(lines).strip()


def format_article_link(article: Article) -> str:
    """Format an article link with domain display text.

    :param article: The article to format.
    :returns: HTML link with domain as display text.
    """
    link_url = article.url_parsed or article.url
    domain = urlparse(link_url).netloc
    return f'<a href="{link_url}">{domain}</a>'
```

### Updated Dagster Op

```python
# src/dagster/newsletters/ops.py (updated)

from dagster import op, OpExecutionContext

from src.database.connection import get_session
from src.newsletters.alert_service import NewsletterAlertService
from src.telegram.client import TelegramClient
from src.telegram.utils.config import get_telegram_settings


@op(description="Send unsent newsletters via Telegram")
def send_newsletter_alerts_op(context: OpExecutionContext) -> None:
    """Send all unsent newsletters as Telegram alerts."""
    settings = get_telegram_settings()

    with get_session() as session:
        client = TelegramClient(
            bot_token=settings.bot_token,
            chat_id=settings.chat_id,
        )
        alert_service = NewsletterAlertService(session, client)
        result = alert_service.send_unsent_newsletters()

        context.log.info(
            f"Newsletter alerts: sent={result.newsletters_sent}, "
            f"failed={result.newsletters_failed}"
        )

        for error in result.errors:
            context.log.warning(error)
```

## Migration Path

### Phase 1: Create New Structure
1. Create `src/newsletters/formatters.py` with formatting functions
2. Create `src/newsletters/alert_service.py` with `NewsletterAlertService`
3. Update `src/newsletters/__init__.py` exports
4. Add unit tests for formatters and alert service

### Phase 2: Update Consumers
5. Update `src/dagster/newsletters/ops.py` to use `NewsletterAlertService`

### Phase 3: Remove Old Code
6. Delete `src/telegram/service.py`
7. Remove `TelegramService` from `src/telegram/__init__.py`
8. Delete `testing/telegram/test_service.py`
9. Move `SendResult` model if still needed (or use the new dataclass)

### Phase 4: Cleanup
10. Run `make check` to verify all tests pass
11. Update README if needed

## Benefits

1. **Correct location**: Newsletter logic lives in newsletters module
2. **No redundant wrapper**: Uses `TelegramClient` directly instead of unnecessary `TelegramService`
3. **Testability**: Can test newsletter formatting without telegram mocks
4. **Simpler telegram module**: Only contains telegram-specific code (client, handler, polling)
5. **Extensibility**: Easy to add `ReminderAlertService` for PRD04 following same pattern
6. **Reusability**: Formatters can be used elsewhere (e.g., email notifications)

## File Changes Summary

| File | Change |
|------|--------|
| `src/newsletters/formatters.py` | NEW - Newsletter formatting functions |
| `src/newsletters/alert_service.py` | NEW - NewsletterAlertService class |
| `src/newsletters/__init__.py` | MODIFY - Add exports |
| `src/telegram/service.py` | DELETE |
| `src/telegram/__init__.py` | MODIFY - Remove TelegramService export |
| `src/telegram/models.py` | MODIFY - Remove SendResult (use dataclass in alert_service) |
| `src/dagster/newsletters/ops.py` | MODIFY - Use NewsletterAlertService |
| `testing/newsletters/test_formatters.py` | NEW - Formatter tests |
| `testing/newsletters/test_alert_service.py` | NEW - AlertService tests |
| `testing/telegram/test_service.py` | DELETE |

## Testing

### Unit Tests for Formatters

```python
class TestFormatNewsletterMessage(unittest.TestCase):
    def test_formats_newsletter_with_articles(self):
        """Test newsletter formatting includes title and articles."""
        ...

    def test_formats_article_link_with_domain(self):
        """Test article link shows domain as display text."""
        ...

    def test_uses_parsed_url_when_available(self):
        """Test url_parsed is preferred over url."""
        ...
```

### Unit Tests for AlertService

```python
class TestNewsletterAlertService(unittest.TestCase):
    def test_send_unsent_newsletters_sends_all(self):
        """Test all unsent newsletters are sent and marked."""
        ...

    def test_handles_send_failure_gracefully(self):
        """Test failed sends are tracked in result."""
        ...

    def test_returns_empty_result_when_no_newsletters(self):
        """Test empty result when nothing to send."""
        ...
```

## Future Considerations

- **ReminderAlertService**: Follow same pattern for PRD04 task/goal reminders
- **Rate Limiting**: Add rate limiting for bulk sends
- **Retry Logic**: Add retry with exponential backoff for failed sends