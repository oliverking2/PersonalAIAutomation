"""SQLAlchemy ORM models for agent conversation and cost tracking."""

import uuid as uuid_module
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base


class AgentConversation(Base):
    """ORM model for tracking multi-run agent conversations."""

    __tablename__ = "agent_conversations"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=False,
        default=Decimal("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Context management columns
    messages_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    selected_tools: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    pending_confirmation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_summarised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_agent_conversations_started_at", "started_at"),
        Index("idx_agent_conversations_external_id", "external_id"),
    )

    def __repr__(self) -> str:
        """Return string representation of the agent conversation."""
        return (
            f"AgentConversation(id={self.id}, external_id={self.external_id}, "
            f"runs={len(self.agent_runs) if self.agent_runs else 0})"
        )


class AgentRun(Base):
    """ORM model for individual agent execution runs."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    conversation_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_conversations.id"),
        nullable=False,
    )
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    steps_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=False,
        default=Decimal("0"),
    )

    conversation: Mapped["AgentConversation"] = relationship(
        "AgentConversation",
        back_populates="agent_runs",
    )
    llm_calls: Mapped[list["LLMCall"]] = relationship(
        "LLMCall",
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_agent_runs_conversation_id", "conversation_id"),
        Index("idx_agent_runs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of the agent run."""
        return f"AgentRun(id={self.id}, stop_reason={self.stop_reason}, steps={self.steps_taken})"


class LLMCall(Base):
    """ORM model for individual LLM API calls."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    agent_run_id: Mapped[uuid_module.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )
    model_alias: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    request_messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    response_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=False,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    agent_run: Mapped["AgentRun | None"] = relationship(
        "AgentRun",
        back_populates="llm_calls",
    )

    __table_args__ = (
        Index("idx_llm_calls_agent_run_id", "agent_run_id"),
        Index("idx_llm_calls_called_at", "called_at"),
        Index("idx_llm_calls_model_alias", "model_alias"),
    )

    def __repr__(self) -> str:
        """Return string representation of the LLM call."""
        return (
            f"LLMCall(id={self.id}, model={self.model_alias}, "
            f"tokens={self.input_tokens}/{self.output_tokens})"
        )
