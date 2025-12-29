"""SQLAlchemy ORM models for Substack newsletters and posts."""

import uuid as uuid_module
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base


class SubstackNewsletter(Base):
    """ORM model for Substack newsletters (publications).

    Stores metadata about Substack publications being tracked.
    Populated from the hardcoded configuration list.
    """

    __tablename__ = "substack_newsletters"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    posts: Mapped[list["SubstackPost"]] = relationship(
        "SubstackPost",
        back_populates="newsletter",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("idx_substack_newsletters_url", "url"),)

    def __repr__(self) -> str:
        """Return string representation of the newsletter."""
        return f"<SubstackNewsletter(id={self.id}, name={self.name!r}, url={self.url!r})>"


class SubstackPost(Base):
    """ORM model for Substack posts.

    Stores individual posts from tracked Substack publications.
    """

    __tablename__ = "substack_posts"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    newsletter_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("substack_newsletters.id"),
        nullable=False,
    )
    post_id: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_paywalled: Mapped[bool] = mapped_column(default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    alerted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    newsletter: Mapped["SubstackNewsletter"] = relationship(
        "SubstackNewsletter",
        back_populates="posts",
    )

    __table_args__ = (
        Index("idx_substack_posts_newsletter_id", "newsletter_id"),
        Index("idx_substack_posts_published_at", "published_at"),
        Index("idx_substack_posts_alerted_at", "alerted_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of the post."""
        return f"<SubstackPost(id={self.id}, title={self.title!r})>"
