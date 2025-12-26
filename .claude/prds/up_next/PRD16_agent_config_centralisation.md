# PRD16: Centralise Agent Configuration Constants

**Status: PROPOSED**

**Roadmap Reference**: AGENT-016

## Overview

Centralise all agent module configuration constants into a single `AgentConfig` class, replacing scattered constants across multiple files.

## Problem Statement

Configuration constants are spread across multiple files in `src/agent/`:

| Constant | Current Location | Purpose |
|----------|------------------|---------|
| `DEFAULT_MAX_STEPS` | `runner.py` | Maximum agent execution steps |
| `DEFAULT_WINDOW_SIZE` | `context_manager.py` | Sliding window message count |
| `DEFAULT_BATCH_THRESHOLD` | `context_manager.py` | Batch summarisation threshold |
| `MODEL_PRICING` | `pricing.py` | LLM cost per token |
| `MAX_CLASSIFICATION_RETRIES` | `confirmation_classifier.py` | Retry limit for parsing |

This causes:
1. **Discoverability**: Hard to find all configurable values
2. **Consistency**: No single source of truth for defaults
3. **Testing**: Difficult to override values in tests
4. **Documentation**: Configuration options not centrally documented

## Proposed Solution

Create `src/agent/config.py` with a dataclass-based configuration:

```python
# src/agent/config.py

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class ModelPricing:
    """Pricing per 1K tokens for a model."""

    input_per_1k: Decimal
    output_per_1k: Decimal
    cache_read_per_1k: Decimal


@dataclass
class AgentConfig:
    """Centralised configuration for the agent module.

    All values have sensible defaults but can be overridden
    at instantiation or via environment variables.
    """

    # Runner settings
    max_steps: int = 5
    tool_timeout_seconds: int = 30

    # Context management
    window_size: int = 15
    batch_threshold: int = 5
    max_message_bytes: int = 1_000_000  # 1MB

    # Classification
    max_classification_retries: int = 2

    # Tool selection
    max_selection_retries: int = 2

    # Model pricing (per 1K tokens)
    model_pricing: dict[str, ModelPricing] = field(default_factory=lambda: {
        "haiku": ModelPricing(
            input_per_1k=Decimal("0.001"),
            output_per_1k=Decimal("0.005"),
            cache_read_per_1k=Decimal("0.0001"),
        ),
        "sonnet": ModelPricing(
            input_per_1k=Decimal("0.003"),
            output_per_1k=Decimal("0.015"),
            cache_read_per_1k=Decimal("0.0003"),
        ),
        "opus": ModelPricing(
            input_per_1k=Decimal("0.005"),
            output_per_1k=Decimal("0.025"),
            cache_read_per_1k=Decimal("0.0005"),
        ),
    })

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables.

        Environment variables (all optional):
        - AGENT_MAX_STEPS: Maximum execution steps
        - AGENT_TOOL_TIMEOUT: Tool execution timeout in seconds
        - AGENT_WINDOW_SIZE: Context window message count
        - AGENT_BATCH_THRESHOLD: Batch summarisation threshold
        """
        import os

        return cls(
            max_steps=int(os.getenv("AGENT_MAX_STEPS", "5")),
            tool_timeout_seconds=int(os.getenv("AGENT_TOOL_TIMEOUT", "30")),
            window_size=int(os.getenv("AGENT_WINDOW_SIZE", "15")),
            batch_threshold=int(os.getenv("AGENT_BATCH_THRESHOLD", "5")),
        )


# Default singleton for convenience
DEFAULT_CONFIG = AgentConfig()
```

## Implementation

### File Changes

| File | Change |
|------|--------|
| `src/agent/config.py` | NEW - AgentConfig class |
| `src/agent/runner.py` | Import and use `config.max_steps`, `config.tool_timeout_seconds` |
| `src/agent/context_manager.py` | Import and use `config.window_size`, `config.batch_threshold` |
| `src/agent/pricing.py` | Import and use `config.model_pricing` |
| `src/agent/confirmation_classifier.py` | Import and use `config.max_classification_retries` |
| `src/agent/__init__.py` | Export `AgentConfig` |

### Usage Pattern

```python
# Before (scattered constants)
DEFAULT_MAX_STEPS = 5

class AgentRunner:
    def __init__(self, max_steps: int = DEFAULT_MAX_STEPS):
        ...

# After (centralised config)
from src.agent.config import AgentConfig, DEFAULT_CONFIG

class AgentRunner:
    def __init__(self, config: AgentConfig = DEFAULT_CONFIG):
        self._config = config
        ...

    def run(self, message: str) -> AgentResponse:
        for step in range(self._config.max_steps):
            ...
```

### Testing Benefits

```python
class TestAgentRunner(unittest.TestCase):
    def test_respects_custom_max_steps(self):
        """Test runner uses configured max_steps."""
        config = AgentConfig(max_steps=3)
        runner = AgentRunner(config=config)
        # Now easy to test with custom config
```

## Migration Steps

1. Create `src/agent/config.py` with `AgentConfig` class
2. Add `ModelPricing` dataclass for pricing structure
3. Update `runner.py` to accept `AgentConfig` parameter
4. Update `context_manager.py` functions to accept config
5. Update `pricing.py` to use `config.model_pricing`
6. Update `confirmation_classifier.py` to use config
7. Remove old constants from individual files
8. Add tests for `AgentConfig.from_env()`
9. Update `.env_example` with new environment variables

## Environment Variables

Add to `.env_example`:

```bash
# Agent Configuration (all optional, shown with defaults)
AGENT_MAX_STEPS=5
AGENT_TOOL_TIMEOUT=30
AGENT_WINDOW_SIZE=15
AGENT_BATCH_THRESHOLD=5
```

## Success Criteria

1. All agent constants defined in single `AgentConfig` class
2. No magic numbers scattered in agent module files
3. Easy to override config in tests
4. Environment variable support for runtime configuration
5. All existing tests pass with default config
