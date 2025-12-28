"""Centralised configuration for the agent module.

All agent configuration values are defined here as the single source of truth.
Use DEFAULT_AGENT_CONFIG for the standard configuration, or instantiate
AgentConfig with custom values for testing.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple


class ModelPricing(NamedTuple):
    """Pricing per 1,000 tokens for a model."""

    input_per_1k: Decimal
    output_per_1k: Decimal
    cache_read_per_1k: Decimal


# Pricing per 1,000 tokens (as of December 2025)
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


@dataclass(frozen=True)
class AgentConfig:
    """Centralised configuration for the agent module.

    All configuration values are defined here as the single source of truth.
    Use DEFAULT_AGENT_CONFIG for the standard configuration, or instantiate
    with custom values for testing.

    :param max_steps: Maximum number of tool execution steps per run.
    :param selector_model: Default model alias for tool selection.
    :param chat_model: Default model alias for chat/tool execution.
    :param max_tokens: Maximum tokens in LLM response. Higher values allow more
        tool calls per response (each tool call requires ~100-200 tokens).
    :param tool_timeout_seconds: Maximum seconds for a single tool execution.
        Prevents hung tools from blocking the agent indefinitely.
    :param window_size: Number of recent messages to keep in full (sliding window).
    :param batch_threshold: Messages above window before summarisation triggers.
    :param max_classification_retries: Maximum retries for confirmation classification.
    :param min_name_length: Minimum characters required for task/goal names.
    :param min_specific_words: Minimum non-vague words required in names.
    """

    # Runner settings
    max_steps: int = 5
    selector_model: str = "haiku"
    chat_model: str = "sonnet"
    max_tokens: int = 4096
    tool_timeout_seconds: float = 30.0

    # Context management
    window_size: int = 15
    batch_threshold: int = 5

    # Classification
    max_classification_retries: int = 2

    # Name validation
    min_name_length: int = 15
    min_specific_words: int = 2


# Default configuration singleton
DEFAULT_AGENT_CONFIG = AgentConfig()
