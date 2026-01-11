"""SQLAlchemy ORM models for agent memory system."""

import secrets
import string
import uuid as uuid_module
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base

# Alphabet for short ID generation: A-Za-z0-9 = 62 characters
# 8 characters = 62^8 ≈ 218 trillion combinations
_SHORT_ID_ALPHABET = string.ascii_letters + string.digits


def generate_short_id() -> str:
    """Generate an 8-character alphanumeric ID for memory entries.

    Uses cryptographically secure random generation for collision resistance.

    :returns: 8-character string from [A-Za-z0-9].
    """
    return "".join(secrets.choice(_SHORT_ID_ALPHABET) for _ in range(8))


class AgentMemory(Base):
    """A logical memory entity - the 'thing' being remembered.

    Memory entries are organised by category and optional subject for efficient
    retrieval and grouping. The actual content is stored in versions to track
    history over time.
    """

    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(
        String(8),
        primary_key=True,
        default=generate_short_id,
    )

    # What this memory is about
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    versions: Mapped[list["AgentMemoryVersion"]] = relationship(
        back_populates="memory",
        order_by="AgentMemoryVersion.version_number",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_agent_memories_category", "category"),
        Index("idx_agent_memories_subject", "subject"),
        Index("idx_agent_memories_deleted_at", "deleted_at"),
    )

    @property
    def is_active(self) -> bool:
        """Check if this memory is active (not deleted).

        :returns: True if deleted_at is None.
        """
        return self.deleted_at is None

    @property
    def current_content(self) -> str | None:
        """Get the latest version's content.

        :returns: Content string from the most recent version, or None if no versions.
        """
        if self.versions:
            return self.versions[-1].content
        return None

    @property
    def current_version(self) -> "AgentMemoryVersion | None":
        """Get the latest version object.

        :returns: The most recent AgentMemoryVersion, or None if no versions.
        """
        if self.versions:
            return self.versions[-1]
        return None

    def __repr__(self) -> str:
        """Return string representation of the memory."""
        status = "active" if self.is_active else "deleted"
        return (
            f"AgentMemory(id={self.id}, category={self.category}, "
            f"subject={self.subject}, status={status})"
        )


class AgentMemoryVersion(Base):
    """A version of a memory's content - tracks history over time.

    Each update to a memory creates a new version, preserving the full history
    of changes with source attribution.
    """

    __tablename__ = "agent_memory_versions"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )

    # Link to parent memory (uses short ID)
    memory_id: Mapped[str] = mapped_column(
        String(8),
        ForeignKey("agent_memories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Version tracking
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Source tracking
    source_conversation_id: Mapped[uuid_module.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_conversations.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    memory: Mapped["AgentMemory"] = relationship(back_populates="versions")

    __table_args__ = (
        Index("idx_memory_versions_memory_id", "memory_id"),
        Index("idx_memory_versions_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of the memory version."""
        return (
            f"AgentMemoryVersion(id={self.id}, memory_id={self.memory_id}, "
            f"version={self.version_number})"
        )
