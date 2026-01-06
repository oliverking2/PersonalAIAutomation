"""SQLAlchemy ORM models for user reminders."""

import uuid as uuid_module
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base

# Maximum length of message to show in repr
REPR_MESSAGE_MAX_LENGTH = 50


class ReminderStatus(StrEnum):
    """Status of a reminder instance."""

    PENDING = "pending"  # Waiting to be sent
    ACTIVE = "active"  # Has been sent, awaiting acknowledgement
    SNOOZED = "snoozed"  # Temporarily delayed
    ACKNOWLEDGED = "acknowledged"  # User confirmed
    EXPIRED = "expired"  # Max attempts reached without acknowledgement


class ReminderSchedule(Base):
    """ORM model for reminder schedules.

    Defines when reminders should trigger. Can be one-time (cron_schedule=NULL)
    or recurring (cron_schedule set). Each trigger creates a ReminderInstance.
    """

    __tablename__ = "reminder_schedules"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    cron_schedule: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    next_trigger_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    instances: Mapped[list["ReminderInstance"]] = relationship(
        "ReminderInstance",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_reminder_schedules_next_trigger", "next_trigger_at", "is_active"),
        Index("idx_reminder_schedules_chat_id", "chat_id"),
    )

    @property
    def is_recurring(self) -> bool:
        """Check if this is a recurring reminder."""
        return self.cron_schedule is not None

    def __repr__(self) -> str:
        """Return string representation of the schedule."""
        if len(self.message) > REPR_MESSAGE_MAX_LENGTH:
            message_preview = self.message[:REPR_MESSAGE_MAX_LENGTH] + "..."
        else:
            message_preview = self.message
        recurrence = f"cron={self.cron_schedule}" if self.is_recurring else "one-time"
        return f"<ReminderSchedule(id={self.id}, message={message_preview!r}, {recurrence})>"


class ReminderInstance(Base):
    """ORM model for reminder instances.

    A triggered reminder awaiting acknowledgement. Created when a schedule
    triggers. Re-sends every 30 minutes until acknowledged or max attempts
    reached (default 3).
    """

    __tablename__ = "reminder_instances"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    schedule_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reminder_schedules.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReminderStatus.PENDING.value,
    )
    send_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_sends: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_send_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    schedule: Mapped["ReminderSchedule"] = relationship(
        "ReminderSchedule",
        back_populates="instances",
    )

    __table_args__ = (
        Index("idx_reminder_instances_status_next_send", "status", "next_send_at"),
        Index("idx_reminder_instances_schedule_id", "schedule_id"),
    )

    def __repr__(self) -> str:
        """Return string representation of the instance."""
        return (
            f"<ReminderInstance(id={self.id}, status={self.status}, "
            f"send_count={self.send_count}/{self.max_sends})>"
        )
