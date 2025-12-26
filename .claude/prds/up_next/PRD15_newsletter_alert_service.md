# PRD15: Newsletter Alert Service Refactor

**Status: PROPOSED**

## Overview

Refactor the `TelegramService` to separate newsletter-specific concerns into a dedicated `NewsletterAlertService`. This improves separation of concerns, making `TelegramService` a thin messaging layer and centralising newsletter alerting logic.

## Problem Statement

The current `TelegramService` mixes two responsibilities:

1. **Generic messaging**: Sending messages via Telegram (`send_message`)
2. **Newsletter-specific logic**: Formatting newsletters, tracking sent state, querying unsent newsletters

This coupling causes:
- Newsletter logic embedded in telegram module instead of newsletters module
- `TelegramService` has database dependencies (`Session`) for newsletter state tracking
- Harder to add new notification types (e.g., reminders from PRD04) without bloating `TelegramService`
- Testing newsletter formatting requires mocking telegram infrastructure

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      TelegramService                            │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐ │
│  │ send_message()  │  │ send_unsent_newsletters()            │ │
│  │ (generic)       │  │ _format_newsletter_message()         │ │
│  │                 │  │ _format_article_link()               │ │
│  │                 │  │ _mark_newsletter_sent()              │ │
│  └─────────────────┘  └──────────────────────────────────────┘ │
│         ↓                          ↓                            │
│  TelegramClient              Session (DB)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Current Files

```python
# src/telegram/service.py (current)
class TelegramService:
    def __init__(self, client: TelegramClient, session: Session) -> None:
        self._client = client
        self._session = session

    def send_message(self, text: str, parse_mode: str = "HTML") -> dict[str, Any]:
        """Send a message via Telegram."""
        return self._client.send_message(text, parse_mode)

    def send_unsent_newsletters(self) -> SendResult:
        """Query unsent newsletters and send them."""
        # Newsletter-specific logic here
        unsent = get_unsent_newsletters(self._session)
        for newsletter in unsent:
            message = self._format_newsletter_message(newsletter)
            self.send_message(message)
            self._mark_newsletter_sent(newsletter)
        ...

    def _format_newsletter_message(self, newsletter: Newsletter) -> str:
        """Format newsletter for Telegram."""
        ...

    def _format_article_link(self, article: NewsletterArticle) -> str:
        """Format article as HTML link."""
        ...
```

## Proposed Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                     NewsletterAlertService                            │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ send_unsent_newsletters()                                        ││
│  │ format_newsletter_message()                                      ││
│  │ format_article_link()                                            ││
│  └──────────────────────────────────────────────────────────────────┘│
│              ↓                              ↓                         │
│       TelegramService                   Session (DB)                  │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                       TelegramService (simplified)                    │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ send_message(text, parse_mode)  # generic messaging only         ││
│  └──────────────────────────────────────────────────────────────────┘│
│                               ↓                                       │
│                        TelegramClient                                 │
└───────────────────────────────────────────────────────────────────────┘
```

## Implementation

### New Files

```
src/newsletters/
├── __init__.py          # (existing)
├── alert_service.py     # NEW: NewsletterAlertService
├── formatters.py        # NEW: Newsletter message formatting
└── tldr/                # (existing)
```

### NewsletterAlertService

```python
# src/newsletters/alert_service.py

from sqlalchemy.orm import Session

from src.database.newsletters.models import Newsletter
from src.database.newsletters.operations import get_unsent_newsletters, mark_newsletter_sent
from src.newsletters.formatters import format_newsletter_message
from src.telegram.service import TelegramService


class SendResult:
    """Result of sending newsletter alerts."""

    def __init__(
        self,
        newsletters_sent: int = 0,
        newsletters_failed: int = 0,
        errors: list[str] | None = None,
    ) -> None:
        self.newsletters_sent = newsletters_sent
        self.newsletters_failed = newsletters_failed
        self.errors = errors or []


class NewsletterAlertService:
    """Service for sending newsletter alerts via Telegram.

    Handles querying unsent newsletters, formatting messages,
    sending via Telegram, and tracking sent state.
    """

    def __init__(
        self,
        telegram_service: TelegramService,
        session: Session,
    ) -> None:
        """Initialise the newsletter alert service.

        :param telegram_service: Service for sending Telegram messages.
        :param session: Database session for newsletter operations.
        """
        self._telegram = telegram_service
        self._session = session

    def send_unsent_newsletters(self) -> SendResult:
        """Query and send all unsent newsletters.

        Fetches newsletters that haven't been sent yet, formats them
        for Telegram, sends them, and marks them as sent.

        :returns: Result with count of sent/failed newsletters.
        """
        unsent = get_unsent_newsletters(self._session)

        if not unsent:
            return SendResult()

        sent_count = 0
        failed_count = 0
        errors: list[str] = []

        for newsletter in unsent:
            try:
                message = format_newsletter_message(newsletter)
                self._telegram.send_message(message)
                mark_newsletter_sent(self._session, newsletter.id)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to send newsletter {newsletter.id}: {e}")

        return SendResult(
            newsletters_sent=sent_count,
            newsletters_failed=failed_count,
            errors=errors if errors else None,
        )
```

### Newsletter Formatters

```python
# src/newsletters/formatters.py

from src.database.newsletters.models import Newsletter, NewsletterArticle


def format_newsletter_message(newsletter: Newsletter) -> str:
    """Format a newsletter for Telegram display.

    :param newsletter: Newsletter with articles to format.
    :returns: HTML-formatted message string.
    """
    lines = [
        f"<b>{newsletter.name}</b>",
        f"<i>{newsletter.edition_date.strftime('%d %B %Y')}</i>",
        "",
    ]

    for article in newsletter.articles:
        lines.append(format_article_link(article))

    return "\n".join(lines)


def format_article_link(article: NewsletterArticle) -> str:
    """Format an article as an HTML link for Telegram.

    :param article: Article to format.
    :returns: HTML anchor tag string.
    """
    # Escape HTML entities in title
    title = (
        article.title
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'• <a href="{article.url}">{title}</a>'
```

### Simplified TelegramService

```python
# src/telegram/service.py (refactored)

from typing import Any

from src.telegram.client import TelegramClient


class TelegramService:
    """Service for sending messages via Telegram.

    This is a thin wrapper around TelegramClient that provides
    a consistent interface for sending messages.
    """

    def __init__(self, client: TelegramClient) -> None:
        """Initialise the Telegram service.

        :param client: Telegram Bot API client.
        """
        self._client = client

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """Send a message via Telegram.

        :param text: Message text to send.
        :param parse_mode: Telegram parse mode (HTML, Markdown, etc.).
        :returns: Telegram API response.
        """
        return self._client.send_message(text, parse_mode)
```

### Updated Dagster Op

```python
# src/dagster/newsletters/ops.py (updated)

from dagster import op, OpExecutionContext

from src.database.newsletters.operations import get_session
from src.newsletters.alert_service import NewsletterAlertService
from src.telegram.client import TelegramClient
from src.telegram.service import TelegramService


@op(description="Send unsent newsletters via Telegram")
def send_newsletter_alerts_op(context: OpExecutionContext) -> None:
    """Send all unsent newsletters as Telegram alerts."""
    with get_session() as session:
        telegram_client = TelegramClient.from_env()
        telegram_service = TelegramService(telegram_client)
        alert_service = NewsletterAlertService(telegram_service, session)

        result = alert_service.send_unsent_newsletters()

        context.log.info(
            f"Newsletter alerts: sent={result.newsletters_sent}, "
            f"failed={result.newsletters_failed}"
        )

        if result.errors:
            for error in result.errors:
                context.log.warning(error)
```

## Migration Path

### Phase 1: Create New Structure
1. Create `src/newsletters/formatters.py` with formatting functions
2. Create `src/newsletters/alert_service.py` with `NewsletterAlertService`
3. Add unit tests for formatters and alert service

### Phase 2: Update Consumers
4. Update `src/dagster/newsletters/ops.py` to use `NewsletterAlertService`
5. Update any other code that uses `TelegramService.send_unsent_newsletters()`

### Phase 3: Simplify TelegramService
6. Remove newsletter methods from `TelegramService`
7. Remove `Session` dependency from `TelegramService.__init__`
8. Update `TelegramService` tests

### Phase 4: Cleanup
9. Run `make check` to verify all tests pass
10. Update README if needed

## Benefits

1. **Separation of Concerns**: Newsletter logic in newsletters module, telegram logic in telegram module
2. **Testability**: Can test newsletter formatting without telegram mocks
3. **Extensibility**: Easy to add `ReminderAlertService` for PRD04 following same pattern
4. **Simpler TelegramService**: No database dependency, single responsibility
5. **Reusability**: Formatters can be used elsewhere (e.g., email notifications)

## File Changes Summary

| File | Change |
|------|--------|
| `src/newsletters/formatters.py` | NEW - Newsletter formatting functions |
| `src/newsletters/alert_service.py` | NEW - NewsletterAlertService class |
| `src/telegram/service.py` | MODIFY - Remove newsletter methods, Session |
| `src/dagster/newsletters/ops.py` | MODIFY - Use NewsletterAlertService |
| `testing/newsletters/test_formatters.py` | NEW - Formatter tests |
| `testing/newsletters/test_alert_service.py` | NEW - AlertService tests |
| `testing/telegram/test_service.py` | MODIFY - Update for simplified service |

## Testing

### Unit Tests for Formatters

```python
class TestFormatNewsletterMessage(unittest.TestCase):
    def test_formats_newsletter_with_articles(self):
        """Test newsletter formatting includes title and articles."""
        newsletter = Newsletter(
            name="TLDR AI",
            edition_date=date(2025, 1, 15),
            articles=[
                NewsletterArticle(title="Article 1", url="https://example.com/1"),
                NewsletterArticle(title="Article 2", url="https://example.com/2"),
            ],
        )
        result = format_newsletter_message(newsletter)
        self.assertIn("<b>TLDR AI</b>", result)
        self.assertIn("15 January 2025", result)
        self.assertIn("Article 1", result)

    def test_escapes_html_in_title(self):
        """Test HTML entities are escaped in article titles."""
        article = NewsletterArticle(
            title="AI & ML: <New> Trends",
            url="https://example.com",
        )
        result = format_article_link(article)
        self.assertIn("AI &amp; ML", result)
        self.assertIn("&lt;New&gt;", result)
```

### Integration Tests for AlertService

```python
class TestNewsletterAlertService(unittest.TestCase):
    def test_send_unsent_newsletters_sends_all(self):
        """Test all unsent newsletters are sent and marked."""
        # Mock telegram service and session
        ...

    def test_handles_send_failure_gracefully(self):
        """Test failed sends are tracked in result."""
        ...
```

## Future Considerations

- **ReminderAlertService**: Follow same pattern for PRD04 reminders
- **NotificationService**: Abstract base class for different notification channels
- **Rate Limiting**: Add rate limiting for bulk sends
- **Retry Logic**: Add retry with exponential backoff for failed sends
