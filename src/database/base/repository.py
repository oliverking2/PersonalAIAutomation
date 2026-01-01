"""Generic database repository utilities.

These functions provide common database operations that can be used across
different newsletter/digest models without duplication.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def compute_url_hash(url: str) -> str:
    """Compute SHA256 hash of a URL for deduplication.

    Normalises the URL by lowercasing, stripping whitespace, and removing
    trailing slashes before hashing.

    :param url: The URL to hash.
    :returns: The hex-encoded SHA256 hash (64 characters).
    """
    normalised = url.lower().strip().rstrip("/")
    return hashlib.sha256(normalised.encode()).hexdigest()


def record_exists_by_field[T](
    session: Session,
    model_class: type[T],
    field_name: str,
    field_value: Any,
) -> bool:
    """Check if a record exists with a specific field value.

    :param session: The database session.
    :param model_class: The SQLAlchemy model class.
    :param field_name: The name of the field to filter by.
    :param field_value: The value to match.
    :returns: True if a matching record exists.
    """
    field = getattr(model_class, field_name)
    return session.query(model_class).filter(field == field_value).first() is not None


def get_unsent_by_alerted_at[T](
    session: Session,
    model_class: type[T],
    order_by_field: str = "received_at",
) -> list[T]:
    """Get all records where alerted_at is NULL.

    :param session: The database session.
    :param model_class: The SQLAlchemy model class (must have alerted_at field).
    :param order_by_field: The field to order results by (ascending).
    :returns: List of records where alerted_at is NULL.
    """
    alerted_at = getattr(model_class, "alerted_at")
    order_field = getattr(model_class, order_by_field)
    return session.query(model_class).filter(alerted_at.is_(None)).order_by(order_field.asc()).all()


def mark_alerted[T](
    session: Session,
    model_class: type[T],
    record_id: uuid.UUID,
) -> None:
    """Mark a record as alerted by setting alerted_at to now.

    :param session: The database session.
    :param model_class: The SQLAlchemy model class.
    :param record_id: The UUID of the record to mark.
    """
    id_field = getattr(model_class, "id")
    record = session.query(model_class).filter(id_field == record_id).one()
    setattr(record, "alerted_at", datetime.now(UTC))
    session.flush()
    logger.debug(f"{model_class.__name__} {record_id} marked as alerted")
