"""Service layer for sending Telegram alerts about newsletters."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.database.models.newsletters import Newsletter
from src.telegram.client import TelegramClient, TelegramClientError
from src.telegram.models import SendResult

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for sending newsletter alerts via Telegram."""

    def __init__(self, session: Session, client: TelegramClient) -> None:
        """Initialise the Telegram service.

        :param session: A SQLAlchemy database session.
        :param client: An initialised TelegramClient.
        """
        self._session = session
        self._client = client

    def send_unsent_newsletters(self) -> SendResult:
        """Send Telegram alerts for all newsletters that haven't been alerted yet.

        :returns: A SendResult with statistics about the operation.
        """
        result = SendResult()

        # Query newsletters where alerted_at is NULL
        unsent_newsletters = (
            self._session.query(Newsletter)
            .filter(Newsletter.alerted_at.is_(None))
            .order_by(Newsletter.received_at.asc())
            .all()
        )

        logger.info(f"Found {len(unsent_newsletters)} newsletters to alert")

        for newsletter in unsent_newsletters:
            try:
                self._send_newsletter_alert(newsletter)
                result.newsletters_sent += 1
            except TelegramClientError as e:
                error_msg = f"Failed to send alert for newsletter {newsletter.id}: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)

        logger.info(
            f"Notification sending complete: {result.newsletters_sent} sent, {len(result.errors)} errors"
        )

        return result

    def _send_newsletter_alert(self, newsletter: Newsletter) -> None:
        """Send a Telegram alert for a single newsletter.

        :param newsletter: The newsletter to send an alert for.
        :raises TelegramClientError: If sending the message fails.
        """
        message = self._format_newsletter_message(newsletter)
        self._client.send_message(message)

        # Mark newsletter as alerted
        newsletter.alerted_at = datetime.now(UTC)
        self._session.flush()

        logger.debug(f"Newsletter {newsletter.id} marked as alerted")

    def _format_newsletter_message(self, newsletter: Newsletter) -> str:
        """Format a newsletter into a Telegram message.

        :param newsletter: The newsletter to format.
        :returns: The formatted message string.
        """
        lines = [f"<b>{newsletter.subject}</b>", ""]

        for article in newsletter.articles:
            lines.append(f"- {article.title}")
            lines.append(f"  {article.url}")
            lines.append("")

        return "\n".join(lines).strip()
