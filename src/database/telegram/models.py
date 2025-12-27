"""SQLAlchemy ORM models for Telegram session and message tracking."""

import uuid as uuid_module
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base

# Maximum length of content to show in repr
REPR_CONTENT_MAX_LENGTH = 50


class TelegramSession(Base):
    """ORM model for Telegram chat sessions.

    A session represents an active conversation period with a specific
    Telegram chat. Sessions expire after a configurable inactivity period.
    Each session is linked to an AgentConversation for AI interaction state.
    """

    __tablename__ = "telegram_sessions"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    chat_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    agent_conversation_id: Mapped[uuid_module.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_conversations.id"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    messages: Mapped[list["TelegramMessage"]] = relationship(
        "TelegramMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TelegramMessage.created_at",
    )

    __table_args__ = (
        Index("idx_telegram_sessions_chat_id_active", "chat_id", "is_active"),
        Index("idx_telegram_sessions_last_activity", "last_activity_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of the session."""
        return f"TelegramSession(id={self.id}, chat_id={self.chat_id}, is_active={self.is_active})"


class TelegramMessage(Base):
    """ORM model for persisted Telegram messages.

    Stores both user messages and assistant responses for audit
    and debugging purposes.
    """

    __tablename__ = "telegram_messages"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    session_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_sessions.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    telegram_message_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    session: Mapped["TelegramSession"] = relationship(
        "TelegramSession",
        back_populates="messages",
    )

    __table_args__ = (
        Index("idx_telegram_messages_session_id", "session_id"),
        Index("idx_telegram_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of the message."""
        if len(self.content) > REPR_CONTENT_MAX_LENGTH:
            content_preview = self.content[:REPR_CONTENT_MAX_LENGTH] + "..."
        else:
            content_preview = self.content
        return f"TelegramMessage(id={self.id}, role={self.role}, content={content_preview!r})"


class TelegramPollingCursor(Base):
    """ORM model for storing the Telegram polling offset.

    Stores the last processed update_id to ensure no messages are
    missed or duplicated when using long polling.
    """

    __tablename__ = "telegram_polling_cursor"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
    )
    last_update_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """Return string representation of the cursor."""
        return f"TelegramPollingCursor(last_update_id={self.last_update_id})"
