"""Service layer for sending Telegram alerts about newsletters."""

import logging
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from src.database.newsletters import (
    Article,
    Newsletter,
    get_unsent_newsletters,
    mark_newsletter_alerted,
)
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

        unsent_newsletters = get_unsent_newsletters(self._session)

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
            f"Notification sending complete: {result.newsletters_sent} sent, "
            f"{len(result.errors)} errors"
        )

        return result

    def _send_newsletter_alert(self, newsletter: Newsletter) -> None:
        """Send a Telegram alert for a single newsletter.

        :param newsletter: The newsletter to send an alert for.
        :raises TelegramClientError: If sending the message fails.
        """
        message = self._format_newsletter_message(newsletter)
        self._client.send_message(message)

        mark_newsletter_alerted(self._session, newsletter.id)

    def _format_newsletter_message(self, newsletter: Newsletter) -> str:
        """Format a newsletter into a Telegram message.

        :param newsletter: The newsletter to format.
        :returns: The formatted message string.
        """
        lines = [f"<b>{newsletter.newsletter_type.value} - {newsletter.subject}</b>", ""]

        for article in newsletter.articles:
            lines.append(f"<b>{article.title}</b>")
            if article.description:
                lines.append(f"{article.description[:150]}")
            lines.append(self._format_article_link(article))
            lines.append("")

        return "\n".join(lines).strip()

    def _format_article_link(self, article: Article) -> str:
        """Format an article link with domain display text.

        :param article: The article to format.
        :returns: HTML link with domain as display text.
        """
        # Use url_parsed if available, otherwise fall back to url
        link_url = article.url_parsed or article.url
        domain = urlparse(link_url).netloc
        return f'<a href="{link_url}">{domain}</a>'
