"""SQLAlchemy ORM models for the database."""

import uuid as uuid_module
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base
from src.newsletters.tldr.models import NewsletterType


class Newsletter(Base):
    """ORM model for newsletters table."""

    __tablename__ = "newsletters"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    email_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    newsletter_type: Mapped[NewsletterType] = mapped_column(
        Enum(NewsletterType, name="newsletter_type_enum"),
        nullable=False,
    )
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

    articles: Mapped[list["Article"]] = relationship(
        "Article",
        back_populates="newsletter",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_newsletters_received_at", "received_at"),
        Index("idx_newsletters_type", "newsletter_type"),
    )

    def __repr__(self) -> str:
        """Return string representation of the newsletter."""
        return f"<Newsletter(id={self.id}, type={self.newsletter_type}, subject={self.subject!r})>"


class Article(Base):
    """ORM model for articles table."""

    __tablename__ = "articles"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    newsletter_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newsletters.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    url_parsed: Mapped[str] = mapped_column(String(2000), nullable=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    newsletter: Mapped["Newsletter"] = relationship(
        "Newsletter",
        back_populates="articles",
    )

    __table_args__ = (
        Index("idx_articles_url_hash", "url_hash"),
        Index("idx_articles_newsletter_id", "newsletter_id"),
    )

    def __repr__(self) -> str:
        """Return string representation of the article."""
        return f"<Article(id={self.id}, title={self.title!r})>"
