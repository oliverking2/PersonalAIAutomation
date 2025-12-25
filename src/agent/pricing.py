"""Pricing configuration for LLM models."""

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


def calculate_cost(
    model_alias: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> Decimal:
    """Calculate estimated cost for an LLM call.

    :param model_alias: Model alias (haiku, sonnet, opus).
    :param input_tokens: Number of input tokens.
    :param output_tokens: Number of output tokens.
    :param cache_read_tokens: Number of cache read tokens.
    :returns: Estimated cost in USD.
    :raises ValueError: If model_alias is not recognised.
    """
    pricing = MODEL_PRICING.get(model_alias.lower())
    if pricing is None:
        raise ValueError(f"Unknown model alias: {model_alias}")

    input_cost = (Decimal(input_tokens) / 1000) * pricing.input_per_1k
    output_cost = (Decimal(output_tokens) / 1000) * pricing.output_per_1k
    cache_cost = (Decimal(cache_read_tokens) / 1000) * pricing.cache_read_per_1k

    return input_cost + output_cost + cache_cost
