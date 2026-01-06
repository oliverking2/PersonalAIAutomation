# Configuration

Rules for managing configuration and environment variables.

## Environment Variables

- Use `.env` for local development (never commit).
- Document all required variables in `.env_example`.
- Access via `python-dotenv` and `os.environ`.

```python
import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.environ.get("API_TOKEN")
DATABASE_URL = os.environ["DATABASE_URL"]  # Required - will raise if missing
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
```

## Never Hard-Code Configuration

```python
# Bad: Hard-coded values
client = APIClient(token="sk-12345", base_url="https://api.example.com")

# Good: From environment
client = APIClient(
    token=os.environ["API_TOKEN"],
    base_url=os.environ.get("API_BASE_URL", "https://api.example.com"),
)
```

## Pydantic Settings

For structured configuration with validation, use `pydantic-settings`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Configuration for the service."""

    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    api_token: str
    base_url: str = "https://api.example.com"
    timeout_seconds: int = 30
    debug: bool = False


# Usage
settings = ServiceSettings()
client = APIClient(token=settings.api_token, timeout=settings.timeout_seconds)
```

## Frozen Dataclasses

For internal configuration that shouldn't change at runtime:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the agent runtime."""

    max_iterations: int = 10
    timeout_seconds: int = 120
    model_id: str = "claude-3-sonnet"
    temperature: float = 0.7


DEFAULT_CONFIG = AgentConfig()
```

## Configuration Patterns

### Centralised Configuration

Keep all configuration in one place per module:

```python
# src/module/config.py
import os

# Required settings (will raise if missing)
API_TOKEN = os.environ["MODULE_API_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Optional settings with defaults
TIMEOUT = int(os.environ.get("MODULE_TIMEOUT", "30"))
DEBUG = os.environ.get("MODULE_DEBUG", "false").lower() == "true"
MAX_RETRIES = int(os.environ.get("MODULE_MAX_RETRIES", "3"))
```

### FastAPI Dependencies

For configuration in FastAPI:

```python
from functools import lru_cache
from fastapi import Depends


@lru_cache
def get_settings() -> ServiceSettings:
    return ServiceSettings()


@router.get("/items")
def list_items(settings: ServiceSettings = Depends(get_settings)):
    client = APIClient(token=settings.api_token)
    return client.list()
```

## Secrets

### Never Log Secrets

```python
# Bad
logger.info(f"Connecting with token: {api_token}")

# Good
logger.info(f"Connecting with token: {'*' * 8}...{api_token[-4:]}")
# Or just don't log it at all
logger.info("Connecting to API")
```

### Don't Commit Secrets

- Add `.env` to `.gitignore`
- Use `.env_example` with placeholder values for documentation
- Consider using a secrets manager for production

```bash
# .env_example
API_TOKEN=your-api-token-here
DATABASE_URL=postgresql://user:password@localhost/dbname
```

## Timeouts

Always configure timeouts for external services:

```python
# From environment or default
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "30"))

# In client
response = requests.get(url, timeout=REQUEST_TIMEOUT)
```

## Feature Flags

For optional features, use boolean environment variables:

```python
ENABLE_CACHING = os.environ.get("ENABLE_CACHING", "true").lower() == "true"
ENABLE_METRICS = os.environ.get("ENABLE_METRICS", "false").lower() == "true"

if ENABLE_CACHING:
    cache = setup_cache()
```
