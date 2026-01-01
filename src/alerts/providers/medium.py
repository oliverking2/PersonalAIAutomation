"""Medium digest alert provider."""

from src.alerts.base.provider import BaseAlertProvider
from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.database.medium import MediumDigest


class MediumAlertProvider(BaseAlertProvider[MediumDigest]):
    """Provider for Medium digest alerts using database queries."""

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.MEDIUM

    @property
    def model_class(self) -> type[MediumDigest]:
        """The SQLAlchemy model class for this provider."""
        return MediumDigest

    def _record_to_alert(self, digest: MediumDigest) -> AlertData:
        """Convert a Medium digest to alert data.

        :param digest: The digest ORM object.
        :returns: AlertData for the digest.
        """
        items = [
            AlertItem(
                name=article.title,
                url=article.url,
                metadata={"description": article.description or ""},
            )
            for article in digest.articles
        ]

        return AlertData(
            alert_type=AlertType.MEDIUM,
            source_id=str(digest.id),
            title=f"Medium Digest - {digest.subject}",
            items=items,
        )
