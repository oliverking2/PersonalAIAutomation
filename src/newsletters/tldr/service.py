"""Service layer for processing TLDR newsletters."""

import logging
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.newsletters import create_newsletter, newsletter_exists
from src.graph.client import GraphClient
from src.newsletters.tldr.fetcher import extract_email_metadata, fetch_tldr_newsletters
from src.newsletters.tldr.models import ParsedNewsletter
from src.newsletters.tldr.parser import identify_newsletter_type, parse_newsletter_html

logger = logging.getLogger(__name__)


class ProcessingResult(BaseModel):
    """Result of processing newsletters."""

    newsletters_processed: int = 0
    articles_extracted: int = 0
    articles_new: int = 0
    articles_duplicate: int = 0
    errors: list[str] = Field(default_factory=list)
    latest_received_at: datetime | None = None


class NewsletterService:
    """Service for processing TLDR newsletters."""

    def __init__(self, session: Session, graph_client: GraphClient) -> None:
        """Initialise the newsletter service.

        :param session: A SQLAlchemy database session.
        :param graph_client: An authenticated GraphAPI client.
        """
        self._session = session
        self._graph_client = graph_client

    def process_newsletters(
        self,
        *,
        since: datetime | None = None,
        limit: int = 25,
    ) -> ProcessingResult:
        """Fetch, parse, and store newsletters.

        :param since: Only process emails received after this datetime.
        :param limit: Maximum number of emails to process.
        :returns: A ProcessingResult with statistics.
        """
        result = ProcessingResult()

        # Fetch newsletters from Graph API
        messages = fetch_tldr_newsletters(
            self._graph_client,
            since=since,
            limit=limit,
        )

        for message in messages:
            try:
                self._process_single_newsletter(message, result)
            except Exception as e:
                error_msg = f"Failed to process newsletter: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)

        logger.info(
            f"Processing complete: {result.newsletters_processed} newsletters, "
            f"{result.articles_extracted} articles ({result.articles_new} new, "
            f"{result.articles_duplicate} duplicate)"
        )

        return result

    def _process_single_newsletter(
        self,
        message: dict[str, object],
        result: ProcessingResult,
    ) -> None:
        """Process a single newsletter message.

        :param message: The raw email message from Graph API.
        :param result: The ProcessingResult to update.
        """
        metadata = extract_email_metadata(message)
        logger.info(f"Processing newsletter: {metadata['subject']}")

        # Check if already processed
        if newsletter_exists(self._session, metadata["email_id"]):
            logger.debug(f"Newsletter already processed: {metadata['email_id']}")
            return

        # Parse the newsletter
        newsletter_type = identify_newsletter_type(metadata["sender_name"])
        articles = parse_newsletter_html(metadata["body_html"])

        parsed = ParsedNewsletter(
            email_id=metadata["email_id"],
            newsletter_type=newsletter_type,
            subject=metadata["subject"],
            received_at=metadata["received_at"],
            articles=articles,
        )

        # Store in database
        _, new_count, dup_count = create_newsletter(self._session, parsed)

        result.newsletters_processed += 1
        result.articles_extracted += len(articles)
        result.articles_new += new_count
        result.articles_duplicate += dup_count

        # Track the latest received_at for watermark updates
        if result.latest_received_at is None or parsed.received_at > result.latest_received_at:
            result.latest_received_at = parsed.received_at
