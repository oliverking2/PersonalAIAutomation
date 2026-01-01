"""Abstract base class for alert providers."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.database.base import get_unsent_by_alerted_at, mark_alerted

logger = logging.getLogger(__name__)


class BaseAlertProvider[T](ABC):
    """Abstract base class for alert providers.

    This provides a common implementation for providers that:
    - Fetch unsent records from a database table
    - Convert records to AlertData
    - Mark records as alerted after sending

    Subclasses must implement:
    - alert_type: The AlertType enum value
    - model_class: The SQLAlchemy model class
    - _record_to_alert: Convert a record to AlertData
    """

    def __init__(self, session: Session) -> None:
        """Initialise the provider.

        :param session: Database session for queries.
        """
        self._session = session

    @property
    @abstractmethod
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        ...

    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        """The SQLAlchemy model class for this provider."""
        ...

    @abstractmethod
    def _record_to_alert(self, record: T) -> AlertData:
        """Convert a database record to AlertData.

        :param record: The database record.
        :returns: AlertData for the record.
        """
        ...

    def get_pending_alerts(self) -> list[AlertData]:
        """Get records that haven't been alerted yet.

        :returns: List of AlertData for unsent records.
        """
        unsent = get_unsent_by_alerted_at(self._session, self.model_class)
        logger.info(f"Found {len(unsent)} unsent {self.model_class.__name__} records")
        return [self._record_to_alert(record) for record in unsent]

    def mark_sent(self, source_id: str) -> None:
        """Mark a record as alerted.

        :param source_id: The record UUID as a string.
        """
        record_id = uuid.UUID(source_id)
        mark_alerted(self._session, self.model_class, record_id)
        logger.debug(f"Marked {self.model_class.__name__} {source_id} as alerted")


def articles_to_alert_items(
    articles: list[Any],
    url_field: str = "url",
    description_field: str = "description",
) -> list[AlertItem]:
    """Convert a list of article records to AlertItems.

    This is a helper function for providers that have articles/posts.

    :param articles: List of article ORM objects.
    :param url_field: Name of the field containing the URL.
    :param description_field: Name of the field containing the description.
    :returns: List of AlertItem objects.
    """
    items = []
    for article in articles:
        url = getattr(article, url_field, None)
        description = getattr(article, description_field, None) or ""
        items.append(
            AlertItem(
                name=article.title,
                url=str(url) if url else None,
                metadata={"description": description},
            )
        )
    return items
