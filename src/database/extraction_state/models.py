"""SQLAlchemy ORM model for extraction state tracking."""

import uuid as uuid_module
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.core import Base


class ExtractionState(Base):
    """ORM model for tracking extraction watermarks.

    Stores the last processed timestamp for each extraction source,
    allowing incremental processing of data.
    """

    __tablename__ = "extraction_state"

    id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid_module.uuid4,
    )
    source_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    watermark: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("idx_extraction_state_source_id", "source_id"),)

    def __repr__(self) -> str:
        """Return string representation of the extraction state."""
        return f"<ExtractionState(source_id={self.source_id!r}, watermark={self.watermark})>"
