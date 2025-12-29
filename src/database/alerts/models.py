"""SQLAlchemy ORM models for alert tracking."""

import uuid as uuid_module
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.core import Base

# Maximum length of content to show in repr
REPR_CONTENT_MAX_LENGTH = 50


class AlertType(StrEnum):
    """Types of alerts that can be sent."""

    NEWSLETTER = "newsletter"
    DAILY_TASK = "daily_task"
    MONTHLY_GOAL = "monthly_goal"
    WEEKLY_READING = "weekly_reading"
    SUBSTACK = "substack"


class SentAlert(Base):
    """ORM model for tracking sent alerts.

    Tracks all proactive notifications sent via Telegram that are
    not part of an interactive chat session. This includes newsletter
    alerts, daily task reminders, monthly goal reviews, and weekly
    reading list reminders.
    """

    __tablename__ = "sent_alerts"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    alert_type: Mapped[AlertType] = mapped_column(
        String(100),
        nullable=False,
    )
    chat_id: Mapped[str] = mapped_column(
        String(50),
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
    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_sent_alerts_type_sent_at", "alert_type", "sent_at"),
        Index("idx_sent_alerts_source_id", "source_id"),
    )

    def __repr__(self) -> str:
        """Return string representation of the alert."""
        if len(self.content) > REPR_CONTENT_MAX_LENGTH:
            content_preview = self.content[:REPR_CONTENT_MAX_LENGTH] + "..."
        else:
            content_preview = self.content
        return f"SentAlert(id={self.id}, type={self.alert_type}, content={content_preview!r})"
