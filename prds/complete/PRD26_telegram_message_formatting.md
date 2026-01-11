# PRD26: Telegram Message Formatting Standardisation

**Status: Complete**
**Created: 2025-01-11**
**Completed: 2025-01-11**

## Overview

Standardise all Telegram message formatting using the `telegramify-markdown` library with an abstraction layer to support future platform changes (e.g., MS Teams).

## Problem Statement

Agent responses were sent to Telegram with `parse_mode=""` (plain text), meaning no formatting was applied. The LLM naturally generates Markdown formatting:

```
Done! I've created 3 test ideas for you:

1. **Test - Example Idea One** - with notes about demonstrating...
```

Users saw the literal `**` characters instead of bold text.

Additionally, the codebase inconsistently used different parse modes:
- Agent responses: `""` (plain text)
- Reminders: `"HTML"`
- Alerts: `"HTML"` (default)
- Error notifications: `"MarkdownV2"`

## Solution

### Approach: Library with Abstraction Layer

After evaluating options, we chose to:

1. **Use `telegramify-markdown` library** - Purpose-built for converting LLM Markdown to Telegram MarkdownV2
2. **Create an ABC-based abstraction** - `MessageFormatter` interface allows swapping platforms without changing call sites
3. **Standardise error notifications on HTML** - Keep HTML for static messages (error notifications)

### Why This Approach

| Option | Pros | Cons |
|--------|------|------|
| Custom regex converter | No dependencies | Edge cases, maintenance burden |
| `chatgpt-md-converter` | LLM-focused | Outputs HTML, less maintained |
| **`telegramify-markdown`** | Well-maintained, MarkdownV2, handles edge cases | Dependency |

The abstraction layer future-proofs for potential migration to MS Teams or other platforms.

## Technical Design

### MessageFormatter Abstraction

```python
from abc import ABC, abstractmethod

class MessageFormatter(ABC):
    """Abstract base class for message formatters."""

    @abstractmethod
    def format(self, markdown: str) -> tuple[str, str]:
        """Convert Markdown to platform-specific format.

        :returns: Tuple of (formatted_text, parse_mode).
        """
        ...


class TelegramFormatter(MessageFormatter):
    """Formatter for Telegram using MarkdownV2."""

    def format(self, markdown: str) -> tuple[str, str]:
        formatted = telegramify_markdown.markdownify(markdown)
        return formatted, "MarkdownV2"
```

### Usage in polling.py

```python
from src.messaging.telegram.utils.formatting import format_message


async def _send_response(self, chat_id: str, text: str) -> None:
    formatted_text, parse_mode = format_message(text)
    await self._client.send_message(formatted_text, chat_id=chat_id, parse_mode=parse_mode)
```

### System Prompt Guidance

Added to `DEFAULT_SYSTEM_PROMPT` in `runner.py`:

```
## Response Formatting

You can use Markdown formatting in your responses. The following formats are supported:
- **bold** for emphasis or important items
- *italic* for subtle emphasis
- ~~strikethrough~~ for removed or cancelled items
- __underline__ for additional emphasis
- [text](url) for links
- ## Headers for section titles

Use formatting sparingly to improve readability. Don't over-format simple responses.
```

## File Changes

| File | Change |
|------|--------|
| `pyproject.toml` | Added `telegramify-markdown` dependency |
| `src/telegram/utils/formatting.py` | `MessageFormatter` ABC, `TelegramFormatter`, `format_message()`, `escape_html()` |
| `src/telegram/utils/__init__.py` | Export new classes and functions |
| `src/telegram/polling.py` | Use `format_message()` for agent responses |
| `src/agent/runner.py` | Added formatting guidance to system prompt |
| `src/dagster/reminders/ops.py` | Converted error notifications to HTML |
| `src/dagster/alerts/ops.py` | Converted error notifications to HTML |
| `src/dagster/utils/sensors.py` | Converted error notifications to HTML |
| `src/telegram/utils/misc.py` | Removed unused `_escape_md()` |
| `testing/telegram/utils/test_formatting.py` | Tests for formatter abstraction |

## Supported Formatting

Via `telegramify-markdown`:

| Markdown | Telegram MarkdownV2 |
|----------|---------------------|
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `~~strikethrough~~` | `~strikethrough~` |
| `__underline__` | `__underline__` |
| `` `code` `` | `` `code` `` |
| ` ``` ` blocks | ` ``` ` blocks |
| `[text](url)` | `[text](url)` |
| `## Header` | Bold text |
| `> blockquote` | Blockquote |

## Future Platform Support

To add a new platform (e.g., MS Teams):

```python
class MSTeamsFormatter(MessageFormatter):
    """Formatter for MS Teams Adaptive Cards."""

    def format(self, markdown: str) -> tuple[str, str]:
        # Convert to Teams format
        return teams_formatted, "teams"
```

Then update the default formatter or use dependency injection.

## Testing

- 18 unit tests covering:
  - `escape_html()` function
  - `MessageFormatter` interface compliance
  - `TelegramFormatter` implementation
  - `format_message()` convenience function
  - Real agent response formatting

## Success Criteria

- [x] Agent responses render formatting correctly in Telegram
- [x] Error notifications use consistent HTML formatting
- [x] Abstraction layer allows future platform changes
- [x] All tests pass with `make check`
- [x] 91% test coverage maintained
