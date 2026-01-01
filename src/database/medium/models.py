"""SQLAlchemy ORM models for Medium digests."""

import uuid as uuid_module
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base


class MediumDigest(Base):
    """ORM model for Medium Daily Digest emails."""

    __tablename__ = "medium_digests"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    email_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    alerted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    articles: Mapped[list["MediumArticle"]] = relationship(
        "MediumArticle",
        back_populates="digest",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("idx_medium_digests_received_at", "received_at"),)

    def __repr__(self) -> str:
        """Return string representation of the digest."""
        return f"<MediumDigest(id={self.id}, subject={self.subject!r})>"


class MediumArticle(Base):
    """ORM model for Medium articles extracted from digests."""

    __tablename__ = "medium_articles"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    digest_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medium_digests.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    digest: Mapped["MediumDigest"] = relationship(
        "MediumDigest",
        back_populates="articles",
    )

    __table_args__ = (
        Index("idx_medium_articles_url_hash", "url_hash"),
        Index("idx_medium_articles_digest_id", "digest_id"),
    )

    def __repr__(self) -> str:
        """Return string representation of the article."""
        return f"<MediumArticle(id={self.id}, title={self.title!r})>"
