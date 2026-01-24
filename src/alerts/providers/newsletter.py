"""Newsletter alert provider."""

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.alerts.providers.base import BaseAlertProvider
from src.database.newsletters import Newsletter


class NewsletterAlertProvider(BaseAlertProvider[Newsletter]):
    """Provider for newsletter alerts using database queries."""

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.NEWSLETTER

    @property
    def model_class(self) -> type[Newsletter]:
        """The SQLAlchemy model class for this provider."""
        return Newsletter

    def _record_to_alert(self, newsletter: Newsletter) -> AlertData:
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
