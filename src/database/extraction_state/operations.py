"""Database operations for extraction state management."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.database.extraction_state.models import ExtractionState

logger = logging.getLogger(__name__)


def get_watermark(session: Session, source_id: str) -> datetime | None:
    """Get the watermark for a given extraction source.

    :param session: The database session.
    :param source_id: The unique identifier for the extraction source.
    :returns: The watermark datetime, or None if no state exists.
    """
    state = session.query(ExtractionState).filter(ExtractionState.source_id == source_id).first()

    if state is None:
        logger.debug(f"No watermark found for source: {source_id}")
        return None

    logger.debug(f"Retrieved watermark for {source_id}: {state.watermark}")
    return state.watermark


def set_watermark(session: Session, source_id: str, watermark: datetime) -> None:
    """Set or update the watermark for a given extraction source.

    Creates a new extraction state record if one doesn't exist,
    otherwise updates the existing record.

    :param session: The database session.
    :param source_id: The unique identifier for the extraction source.
    :param watermark: The new watermark datetime (must be timezone-aware).
    :raises ValueError: If the watermark is not timezone-aware.
    """
    if watermark.tzinfo is None:
        raise ValueError("Watermark must be timezone-aware")

    state = session.query(ExtractionState).filter(ExtractionState.source_id == source_id).first()

    if state is None:
        state = ExtractionState(
            source_id=source_id,
            watermark=watermark,
        )
        session.add(state)
        logger.info(f"Created watermark for {source_id}: {watermark}")
    else:
        state.watermark = watermark
        state.updated_at = datetime.now(UTC)
        logger.info(f"Updated watermark for {source_id}: {watermark}")

    session.flush()
