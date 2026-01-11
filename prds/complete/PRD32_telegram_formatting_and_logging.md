# PRD32: Telegram Formatting and Logging Improvements

**Status: COMPLETED**

**Roadmap Reference**:
- TELE-010: Migrate alert formatters to Markdown/MarkdownV2
- TELE-005: Structured logging with chat_id, session_id
- TD-003: Inject agent runner instead of lazy init

## Overview

Three related improvements to the Telegram module:

1. **TELE-010**: Migrate all alert formatters from HTML to MarkdownV2 for consistency with agent responses
2. **TELE-005**: Ensure logs consistently include both chat_id and session_id
3. **TD-003**: Remove lazy init fallback for agent runner - require injection

## Problem Statement

### Alert Formatting Issues

All alert formatters currently use HTML parse mode, while agent responses use MarkdownV2:

```python
# Current: Alert formatters (src/alerts/formatters/formatters.py)
def format_newsletter_alert(articles: list[Article]) -> str:
    lines = ["<b>Newsletter Alert</b>"]
    for article in articles:
        lines.append(f"<a href=\"{article.url}\">{article.title}</a>")  # HTML
    return "\n".join(lines)

# Already exists: Agent responses (src/messaging/telegram/utils/formatting.py)
class TelegramFormatter(MessageFormatter):
    def format(self, markdown: str) -> tuple[str, str]:
        formatted = telegramify_markdown.markdownify(markdown)
        return formatted, "MarkdownV2"  # MarkdownV2
```

**Issues with current HTML approach**:
1. **Inconsistent parse modes**: Alerts use HTML, agent responses use MarkdownV2
2. **Missing HTML escaping**: Most formatters don't escape user content (security risk)
3. **Harder to maintain**: Two different formatting paradigms in the codebase
4. **Special character issues**: HTML entities vs Markdown escaping handled differently

### Logging Issues

Current logging includes chat_id but inconsistently:

```python
# Current: chat_id included, but session_id only in some places
logger.info(f"Processing message: chat_id={chat_id}, text={text[:50]}...")
logger.warning(f"Received message from unauthorised chat: chat_id={chat_id}")
logger.exception(f"Agent execution failed: session_id={session.id}, chat_id={session.chat_id}")  # session_id here
logger.debug(f"Sent response to chat_id={chat_id}")  # but not here
```

**Issue**: session_id is only logged in exception handlers, not in routine operations. This makes it harder to trace a full conversation flow in logs.

### Agent Runner Injection Issue

The `MessageHandler` class accepts an optional `agent_runner` parameter but falls back to lazy initialisation if not provided:

```python
# Current: Optional with fallback
class MessageHandler:
    def __init__(self, ..., agent_runner: AgentRunner | None = None):
        self._agent_runner = agent_runner  # Can be None

    def _get_agent_runner(self) -> AgentRunner:
        if self._agent_runner is None:
            self._agent_runner = AgentRunner(...)  # Lazy init
        return self._agent_runner
```

**Issue**: This pattern makes testing harder and hides the dependency. The runner should be required.

## Proposed Solution

### Part 1: Alert Formatter Migration (TELE-010)

#### Strategy

Migrate formatters to output standard Markdown, then use the existing `TelegramFormatter` to convert to MarkdownV2. This follows the pattern already established for agent responses.

#### Current Formatters to Migrate

| Formatter | File | Current | After |
|-----------|------|---------|-------|
| `format_newsletter_alert` | `src/alerts/formatters/formatters.py` | HTML | Markdown |
| `format_task_alert` | `src/alerts/formatters/formatters.py` | HTML | Markdown |
| `format_goal_alert` | `src/alerts/formatters/formatters.py` | HTML | Markdown |
| `format_reading_alert` | `src/alerts/formatters/formatters.py` | HTML | Markdown |
| `format_substack_alert` | `src/alerts/formatters/formatters.py` | HTML | Markdown |
| `format_medium_alert` | `src/alerts/formatters/formatters.py` | HTML | Markdown |
| `format_glitchtip_alert` | `src/api/webhooks/glitchtip/formatter.py` | HTML | Markdown |
| `format_test_alert` | `src/api/webhooks/glitchtip/formatter.py` | HTML | Markdown |

#### Formatting Conversion Table

| HTML | Markdown | Notes |
|------|----------|-------|
| `<b>text</b>` | `**text**` | Bold |
| `<i>text</i>` | `_text_` | Italic |
| `<a href="url">text</a>` | `[text](url)` | Links |
| `<pre>text</pre>` | `` `text` `` | Inline code |
| `<code>text</code>` | `` `text` `` | Inline code |
| `html.escape(text)` | Not needed | `telegramify_markdown` handles escaping |

#### Implementation Pattern

```python
# src/alerts/formatters/formatters.py

from src.messaging.telegram.utils.formatting import TelegramFormatter

_telegram_formatter = TelegramFormatter()


def format_newsletter_alert(articles: list[Article]) -> tuple[str, str]:
    """Format newsletter alert for Telegram.

    :param articles: List of articles to include.
    :returns: Tuple of (formatted_text, parse_mode).
    """
    lines = ["**Newsletter Alert**", ""]

    for article in articles:
        # Markdown link - telegramify_markdown handles escaping
        lines.append(f"- [{article.title}]({article.url})")
        if article.description:
            desc = article.description[:100] + "..." if len(article.description) > 100 else article.description
            lines.append(f"  {desc}")

    markdown = "\n".join(lines)
    return _telegram_formatter.format(markdown)
```

#### Update Alert Service

```python
# src/alerts/service.py

class AlertService:
    async def send_alert(self, alert_type: str, data: Any) -> None:
        formatter = self._get_formatter(alert_type)
        message, parse_mode = formatter(data)  # Now returns tuple

        await self._telegram_client.send_message(
            message,
            parse_mode=parse_mode,  # Use returned parse_mode
        )
```

#### Update Webhook Endpoints

```python
# src/api/webhooks/glitchtip/endpoints.py

def receive_glitchtip_webhook(alert: GlitchTipAlert, ...) -> WebhookResponse:
    message, parse_mode = format_glitchtip_alert(alert)  # Now returns tuple
    client.send_message_sync(message, parse_mode=parse_mode)
    ...
```

### Part 2: Consistent Logging (TELE-005)

#### Strategy

Simply ensure all log statements in the Telegram module consistently include `chat_id` and `session_id` where available. No new infrastructure needed.

#### Pattern

```python
# Standard format for Telegram logs
logger.info(f"Processing message: chat_id={chat_id}, session_id={session_id}")
logger.debug(f"Sent response: chat_id={chat_id}, session_id={session_id}")
logger.exception(f"Agent failed: chat_id={chat_id}, session_id={session_id}")
```

#### Files to Review

Go through these files and add `session_id` to log statements that only have `chat_id`:

- `src/messaging/telegram/handler.py` - most logs already have chat_id, add session_id
- `src/messaging/telegram/polling.py` - add session_id to response logs
- `src/messaging/telegram/client.py` - lower-level, chat_id only is fine here

### Part 3: Agent Runner Injection (TD-003)

#### Strategy

Remove the lazy init fallback and make `agent_runner` a required parameter.

```python
# Before: Optional with lazy fallback
class MessageHandler:
    def __init__(self, ..., agent_runner: AgentRunner | None = None):
        self._agent_runner = agent_runner

    def _get_agent_runner(self) -> AgentRunner:
        if self._agent_runner is None:
            self._agent_runner = AgentRunner(...)
        return self._agent_runner

# After: Required parameter
class MessageHandler:
    def __init__(self, ..., agent_runner: AgentRunner):
        self._agent_runner = agent_runner

    # No lazy init method needed
```

#### Call Sites to Update

Wherever `MessageHandler` is instantiated, ensure an `AgentRunner` is provided:

- `src/messaging/telegram/polling.py` - creates MessageHandler
- `src/messaging/telegram/__main__.py` - entry point

## Implementation Steps

### Part 1: Alert Formatter Migration

1. [x] Update `format_newsletter_alert` to return `(text, parse_mode)` tuple
2. [x] Update `format_task_alert` to return tuple
3. [x] Update `format_goal_alert` to return tuple
4. [x] Update `format_reading_alert` to return tuple
5. [x] Update `format_substack_alert` to return tuple
6. [x] Update `format_medium_alert` to return tuple
7. [x] Update `format_glitchtip_alert` to return tuple
8. [x] Update `format_test_alert` to return tuple
9. [x] Update `AlertService.send_alert()` to use parse_mode from formatter
10. [x] Update GlitchTip webhook endpoints to use parse_mode
11. [x] Update all formatter tests for new return type
12. [ ] Manual testing of each alert type in Telegram

### Part 2: Consistent Logging

1. [x] Review `src/messaging/telegram/handler.py` - add session_id to logs missing it
2. [x] Review `src/messaging/telegram/polling.py` - add session_id to response logs
3. [x] Verify key operations log both chat_id and session_id

### Part 3: Agent Runner Injection

1. [x] Remove lazy init fallback from `MessageHandler.__init__`
2. [x] Make `agent_runner` a required parameter
3. [x] Update all call sites to provide the runner
4. [x] Update tests to inject mock runner

## Files to Modify

### Part 1: Formatter Migration

| File | Changes |
|------|---------|
| `src/alerts/formatters/formatters.py` | Convert 6 formatters to Markdown, return tuples |
| `src/alerts/service.py` | Use parse_mode from formatter return value |
| `src/api/webhooks/glitchtip/formatter.py` | Convert 2 formatters to Markdown |
| `src/api/webhooks/glitchtip/endpoints.py` | Use parse_mode from formatter |
| `testing/alerts/formatters/test_formatters.py` | Update for tuple returns |
| `testing/api/webhooks/glitchtip/test_formatter.py` | Update for tuple returns |

### Part 2: Consistent Logging

| File | Changes |
|------|---------|
| `src/messaging/telegram/handler.py` | Add session_id to logs that only have chat_id |
| `src/messaging/telegram/polling.py` | Add session_id to response logs |

### Part 3: Agent Runner Injection

| File | Changes |
|------|---------|
| `src/messaging/telegram/handler.py` | Make agent_runner required, remove lazy init |
| `src/messaging/telegram/polling.py` | Pass agent_runner when creating MessageHandler |
| `src/messaging/telegram/__main__.py` | Create and pass AgentRunner |
| `testing/messaging/telegram/test_handler.py` | Update to always inject mock runner |

## Testing

### Part 1: Formatter Tests

Update existing tests to expect `(text, parse_mode)` tuple:

```python
class TestFormatNewsletterAlert(unittest.TestCase):
    def test_returns_markdown_and_parse_mode(self) -> None:
        articles = [Article(title="Test", url="https://example.com")]

        text, parse_mode = format_newsletter_alert(articles)

        self.assertEqual(parse_mode, "MarkdownV2")
        self.assertIn("Newsletter Alert", text)
```

### Part 2: Logging

No new tests - just verify logs include session_id by inspection.

### Part 3: Agent Runner Injection

Update handler tests to always provide a mock runner:

```python
class TestMessageHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_runner = MagicMock(spec=AgentRunner)
        self.handler = MessageHandler(
            telegram_client=MagicMock(),
            agent_runner=self.mock_runner,  # Now required
        )
```

### Manual Testing

1. Trigger each alert type and verify formatting in Telegram
2. Check that special characters display correctly
3. Verify logs include both chat_id and session_id

## Alternatives Considered

### Keep HTML for Alerts

- Pros: No migration work, familiar format
- Cons: Inconsistent with agent responses, missing escaping in most formatters
- Decision: Migrate for consistency and security

## Success Criteria

### Part 1: Formatter Migration

1. All alert formatters return `(text, parse_mode)` tuple
2. All formatters output Markdown, not HTML
3. Special characters in user content are properly escaped
4. Visual appearance in Telegram is equivalent to current HTML

### Part 2: Consistent Logging

1. Key log statements in handler.py and polling.py include both chat_id and session_id

### Part 3: Agent Runner Injection

1. `MessageHandler.__init__` requires `agent_runner` parameter (no default)
2. No lazy init method exists
3. All call sites provide an AgentRunner instance
4. Tests inject mock runner

## Dependencies

- `telegramify-markdown` (already installed) - for MarkdownV2 conversion
- No new dependencies required

## Risks

1. **MarkdownV2 edge cases**: Some content may format differently than HTML. Mitigate with manual testing of each alert type.
