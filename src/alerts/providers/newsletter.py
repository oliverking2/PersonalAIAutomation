"""Newsletter alert provider."""

import logging
import uuid

from sqlalchemy.orm import Session

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.database.newsletters import Newsletter, get_unsent_newsletters, mark_newsletter_alerted

logger = logging.getLogger(__name__)


class NewsletterAlertProvider:
    """Provider for newsletter alerts using database queries."""

    def __init__(self, session: Session) -> None:
        """Initialise the provider.

        :param session: Database session for queries.
        """
        self._session = session

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.NEWSLETTER

    def get_pending_alerts(self) -> list[AlertData]:
        """Get newsletters that haven't been alerted yet.

        :returns: List of AlertData for unsent newsletters.
        """
        unsent = get_unsent_newsletters(self._session)
        logger.info(f"Found {len(unsent)} unsent newsletters")
        return [self._newsletter_to_alert(nl) for nl in unsent]

    def mark_sent(self, source_id: str) -> None:
        """Mark a newsletter as alerted.

        :param source_id: The newsletter UUID as a string.
        """
        newsletter_id = uuid.UUID(source_id)
        mark_newsletter_alerted(self._session, newsletter_id)
        logger.debug(f"Marked newsletter {source_id} as alerted")

    def _newsletter_to_alert(self, newsletter: Newsletter) -> AlertData:
        """Convert a newsletter to alert data.

        :param newsletter: The newsletter ORM object.
        :returns: AlertData for the newsletter.
        """
        items = [
            AlertItem(
                name=article.title,
                url=article.url_parsed or article.url,
                metadata={"description": article.description or ""},
            )
            for article in newsletter.articles
        ]

        return AlertData(
            alert_type=AlertType.NEWSLETTER,
            source_id=str(newsletter.id),
            title=f"{newsletter.newsletter_type.value} - {newsletter.subject}",
            items=items,
        )
