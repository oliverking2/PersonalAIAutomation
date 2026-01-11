"""Pricing calculations for LLM models."""

from decimal import Decimal

from src.agent.utils.config import MODEL_PRICING


def calculate_cost(
    model_alias: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    """Calculate estimated cost for an LLM call.

    :param model_alias: Model alias (haiku, sonnet, opus).
    :param input_tokens: Number of input tokens.
    :param output_tokens: Number of output tokens.
    :param cache_read_tokens: Number of cache read tokens (charged at 10% of input).
    :param cache_write_tokens: Number of cache write tokens (charged at 125% of input).
    :returns: Estimated cost in USD.
    :raises ValueError: If model_alias is not recognised.
    """
    pricing = MODEL_PRICING.get(model_alias.lower())
    if pricing is None:
        raise ValueError(f"Unknown model alias: {model_alias}")

    input_cost = (Decimal(input_tokens) / 1000) * pricing.input_per_1k
    output_cost = (Decimal(output_tokens) / 1000) * pricing.output_per_1k
    cache_read_cost = (Decimal(cache_read_tokens) / 1000) * pricing.cache_read_per_1k
    cache_write_cost = (Decimal(cache_write_tokens) / 1000) * pricing.cache_write_per_1k

    return input_cost + output_cost + cache_read_cost + cache_write_cost
