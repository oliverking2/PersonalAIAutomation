"""LLM call tracking context and utilities."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.agent.enums import CallType
from src.agent.utils.pricing import calculate_cost

logger = logging.getLogger(__name__)

# Context variable for current tracking context
_tracking_context: ContextVar[TrackingContext | None] = ContextVar("tracking_context", default=None)


@dataclass
class LLMCallRecord:
    """Record of a single LLM call."""

    id: uuid.UUID
    model_alias: str
    model_id: str
    call_type: CallType
    request_messages: list[dict[str, Any]]
    response_content: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    estimated_cost_usd: Decimal
    latency_ms: int
    called_at: datetime


@dataclass
class TrackingContext:
    """Context for tracking LLM calls.

    Can be used at the agent level (with run_id and conversation_id)
    or at the BedrockClient level for standalone LLM calls.
    """

    llm_calls: list[LLMCallRecord] = field(default_factory=list)
    run_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None

    def record_call(  # noqa: PLR0913 - LLM call tracking requires multiple parameters
        self,
        model_alias: str,
        model_id: str,
        call_type: CallType,
        request_messages: list[dict[str, Any]],
        response: dict[str, Any],
        latency_ms: int,
    ) -> LLMCallRecord:
        """Record an LLM call.

        :param model_alias: Model alias used (haiku, sonnet, opus).
        :param model_id: Full Bedrock model ID.
        :param call_type: Type of call (chat or selector).
        :param request_messages: Messages sent to the LLM.
        :param response: Full response from the LLM.
        :param latency_ms: Call latency in milliseconds.
        :returns: The recorded LLM call.
        """
        usage = response.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        cache_read_tokens = usage.get("cacheReadInputTokenCount", 0)

        cost = calculate_cost(
            model_alias=model_alias,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
        )

        record = LLMCallRecord(
            id=uuid.uuid4(),
            model_alias=model_alias,
            model_id=model_id,
            call_type=call_type,
            request_messages=request_messages,
            response_content=response.get("output", {}),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            called_at=datetime.now(UTC),
        )

        self.llm_calls.append(record)
        logger.debug(
            f"Recorded LLM call: type={call_type}, model={model_alias}, "
            f"tokens={input_tokens}/{output_tokens}, cost=${cost}, latency={latency_ms}ms"
        )

        return record

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens across all calls."""
        return sum(call.input_tokens for call in self.llm_calls)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens across all calls."""
        return sum(call.output_tokens for call in self.llm_calls)

    @property
    def total_cache_read_tokens(self) -> int:
        """Total cache read tokens across all calls."""
        return sum(call.cache_read_tokens for call in self.llm_calls)

    @property
    def total_estimated_cost(self) -> Decimal:
        """Total estimated cost across all calls."""
        return sum((call.estimated_cost_usd for call in self.llm_calls), Decimal("0"))


def get_tracking_context() -> TrackingContext | None:
    """Get the current tracking context.

    :returns: Current tracking context or None if not set.
    """
    return _tracking_context.get()


def set_tracking_context(context: TrackingContext | None) -> None:
    """Set the current tracking context.

    :param context: Tracking context to set, or None to clear.
    """
    _tracking_context.set(context)
