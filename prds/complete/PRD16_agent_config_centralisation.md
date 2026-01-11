# PRD16: Centralise Agent Configuration Constants

**Status: COMPLETE**

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

Create `src/agent/config.py` with a simple frozen dataclass for centralised configuration:

```python
# src/agent/config.py

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPricing:
    """Pricing per 1K tokens for a model."""

    input_per_1k: Decimal
    output_per_1k: Decimal
    cache_read_per_1k: Decimal


@dataclass(frozen=True)
class AgentConfig:
    """Centralised configuration for the agent module.

    All configuration values are defined here as the single source of truth.
    Use DEFAULT_AGENT_CONFIG for the standard configuration, or instantiate
    with custom values for testing.
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


# Model pricing defined separately as it's a nested structure
MODEL_PRICING: dict[str, ModelPricing] = {
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
}

# Default configuration singleton
DEFAULT_AGENT_CONFIG = AgentConfig()
```

### Benefits

1. **Single source of truth**: All constants in one file
2. **Frozen dataclass**: Immutable, hashable, prevents accidental mutation
3. **No external dependencies**: Uses stdlib `dataclasses` only
4. **Easy testing**: Create custom instances with overridden values
5. **Self-documenting**: All options visible in one place with docstrings

## Implementation

### File Changes

| File | Change |
|------|--------|
| `src/agent/config.py` | NEW - AgentConfig class and MODEL_PRICING |
| `src/agent/runner.py` | Import and use `DEFAULT_AGENT_CONFIG.max_steps` |
| `src/agent/context_manager.py` | Import and use `DEFAULT_AGENT_CONFIG.window_size`, etc. |
| `src/agent/pricing.py` | Import `MODEL_PRICING` from config |
| `src/agent/confirmation_classifier.py` | Import and use `DEFAULT_AGENT_CONFIG.max_classification_retries` |
| `src/agent/__init__.py` | Export `AgentConfig`, `DEFAULT_AGENT_CONFIG`, `MODEL_PRICING` |
| `CLAUDE.md` | Document the config module and usage pattern |

### Usage Pattern

```python
# Before (scattered constants)
DEFAULT_MAX_STEPS = 5


class AgentRunner:
    def __init__(self, max_steps: int = DEFAULT_MAX_STEPS):
        ...


# After (centralised config with dependency injection)
from src.agent.utils.config import AgentConfig, DEFAULT_AGENT_CONFIG


class AgentRunner:
    def __init__(self, config: AgentConfig = DEFAULT_AGENT_CONFIG):
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

    def test_default_config_values(self):
        """Test default configuration values."""
        config = AgentConfig()
        self.assertEqual(config.max_steps, 5)
        self.assertEqual(config.window_size, 15)
```

## Migration Steps

1. Create `src/agent/config.py` with `AgentConfig` dataclass
2. Add `ModelPricing` dataclass and `MODEL_PRICING` dict
3. Update `runner.py` to accept `AgentConfig` parameter
4. Update `context_manager.py` functions to accept config
5. Update `pricing.py` to import `MODEL_PRICING` from config
6. Update `confirmation_classifier.py` to use config
7. Remove old constants from individual files
8. Export from `src/agent/__init__.py`
9. Add tests for `AgentConfig`
10. Update `CLAUDE.md` to document the config pattern

## CLAUDE.md Update

Add to the Agent Module Structure section:

```markdown
### Agent Configuration

All agent configuration is centralised in `src/agent/config.py`:

- `AgentConfig`: Frozen dataclass with all tuneable parameters
- `DEFAULT_AGENT_CONFIG`: Default configuration singleton
- `MODEL_PRICING`: Per-model token pricing

When adding new configuration:
1. Add the field to `AgentConfig` with a sensible default
2. Update consuming code to use `config.field_name`
3. Document the field in the class docstring
```

## Success Criteria

1. All agent constants defined in single `AgentConfig` class
2. No magic numbers scattered in agent module files
3. Easy to override config in tests via custom instantiation
4. Frozen dataclass prevents accidental mutation
5. All existing tests pass with default config
6. `CLAUDE.md` documents the configuration pattern
