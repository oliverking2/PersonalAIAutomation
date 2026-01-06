# Module Structure

Rules for organising code within modules.

## Core Module Structure

Non-API modules follow this structure:

```
src/<module>/
├── __init__.py           # Exports public API
├── client.py             # External API client (if applicable)
├── models.py             # Pydantic models for data
├── parser.py             # Data transformation functions
├── enums.py              # StrEnum definitions (if applicable)
├── exceptions.py         # Custom exceptions
└── utils/                # Internal utilities (optional, for larger modules)
    └── config.py         # Configuration using pydantic-settings
```

## Agent Module Structure

The agent module provides AI-powered tool calling:

```
src/agent/
├── __init__.py              # Exports public API
├── bedrock_client.py        # AWS Bedrock Converse API client
├── enums.py                 # RiskLevel, CallType, etc.
├── exceptions.py            # Agent-specific exceptions
├── models.py                # ToolDef, AgentRunResult, etc.
├── runner.py                # AgentRunner orchestrates agent execution
├── tools/                   # Tool definitions by domain
│   ├── factory.py           # CRUD tool factory for reusable patterns
│   ├── models.py            # Tool-specific argument models
│   └── <domain>.py          # Domain-specific tool configurations
└── utils/
    ├── config.py            # AgentConfig centralised configuration
    ├── call_tracking.py     # LLM call tracking and persistence
    ├── context_manager.py   # Conversation context management
    ├── pricing.py           # Token cost calculation
    ├── templates.py         # System prompt templates
    └── tools/
        ├── registry.py      # ToolRegistry for tool management
        └── selector.py      # ToolSelector for intelligent selection
```

### Agent Tool Patterns

Tools use a CRUD factory pattern for consistency:

```python
from src.agent.tools.factory import CRUDToolConfig, create_crud_tools

TASK_TOOLS_CONFIG = CRUDToolConfig(
    domain="task",
    domain_plural="tasks",
    endpoint_prefix="/api/tasks",
    id_field="task_id",
    name_field="task_name",
    query_model=QueryTaskArgs,
    create_model=CreateTaskArgs,
    update_model=UpdateTaskArgs,
    query_description="Query tasks with optional filters.",
    get_description="Get a task by ID.",
    create_description="Create new tasks.",
    update_description="Update an existing task.",
)

TASK_TOOLS = create_crud_tools(TASK_TOOLS_CONFIG)
```

### Agent Configuration

All configuration is centralised:

```python
# src/agent/utils/config.py
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the agent runtime."""

    max_iterations: int = 10
    timeout_seconds: int = 120
    model_id: str = "anthropic.claude-3-sonnet"
    temperature: float = 0.7


DEFAULT_AGENT_CONFIG = AgentConfig()
MODEL_PRICING = {"anthropic.claude-3-sonnet": {"input": 0.003, "output": 0.015}}
```

## Telegram Module Structure

For bot interactions and long-polling:

```
src/telegram/
├── __init__.py           # Exports public API
├── client.py             # TelegramClient for Bot API (async)
├── handler.py            # MessageHandler for processing messages
├── models.py             # TelegramUpdate, TelegramMessage, etc.
├── polling.py            # PollingRunner for long-polling loop
├── service.py            # TelegramService for sending alerts
└── utils/
    ├── config.py         # TelegramSettings (pydantic-settings)
    ├── session_manager.py # Links Telegram chats to conversations
    └── misc.py           # Utility functions
```

### Async Client Pattern

```python
import httpx


class TelegramClient:
    """Async client for Telegram Bot API."""

    def __init__(self, bot_token: str, timeout: float = 30.0) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def send_message(self, chat_id: int, text: str) -> dict:
        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

## Newsletter Module Structure

For content parsing with multiple sources:

```
src/newsletters/
├── __init__.py
├── base/
│   ├── __init__.py
│   └── parser.py         # BaseNewsletterParser abstract class
├── tldr/
│   ├── __init__.py
│   ├── parser.py         # TLDR-specific parser
│   └── models.py         # Parsed article models
├── substack/
│   └── parser.py         # Substack post parser
└── medium/
    └── parser.py         # Medium digest parser
```

### Base Parser Pattern

```python
from abc import ABC, abstractmethod


class BaseNewsletterParser(ABC):
    """Base class for newsletter parsers."""

    @abstractmethod
    def parse(self, html_content: str) -> list[ParsedArticle]:
        """Parse newsletter HTML into articles."""
        pass

    @abstractmethod
    def identify(self, sender: str, subject: str) -> bool:
        """Check if this parser handles the given email."""
        pass
```

## Alerts Module Structure

For pluggable alert providers:

```
src/alerts/
├── __init__.py
├── service.py            # AlertService orchestrates providers
├── base/
│   └── provider.py       # BaseAlertProvider abstract class
├── formatters/
│   └── newsletter.py     # Format articles for alerts
└── providers/
    └── telegram.py       # TelegramAlertProvider implementation
```

### Provider Pattern

```python
from abc import ABC, abstractmethod


class BaseAlertProvider(ABC):
    """Base class for alert providers."""

    @abstractmethod
    async def send(self, message: str, **kwargs) -> bool:
        """Send an alert message."""
        pass

    @abstractmethod
    def format(self, data: dict) -> str:
        """Format data for this provider."""
        pass
```

## General Guidelines

1. **Export public API in `__init__.py`**: Only expose what consumers need
2. **Keep `client.py` focused**: Only HTTP/API interaction logic
3. **Put models in `models.py`**: Pydantic models for domain data
4. **Put enums in `enums.py`**: StrEnum definitions for valid values
5. **Put parsing in `parser.py`**: Data transformation logic
6. **Use `utils/` for helpers**: Internal utilities that don't fit elsewhere
7. **Configuration in `utils/config.py`**: Centralised settings
