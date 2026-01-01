"""Abstract base class for newsletter processing services."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.database.base import record_exists_by_field
from src.graph.client import GraphClient
from src.newsletters.base.fetcher import extract_email_metadata, fetch_emails
from src.newsletters.base.models import ProcessingResult

if TYPE_CHECKING:
    from src.database.core import Base
    from src.newsletters.base.models import ParsedArticleBase, ParsedDigestBase

logger = logging.getLogger(__name__)


class BaseNewsletterService(ABC):
    """Abstract base class for newsletter/digest processing services.

    Subclasses must implement:
    - sender_email: The email address to filter for
    - source_name: Human-readable name for logging
    - db_model_class: The SQLAlchemy model class for persistence
    - _parse_html: Parse HTML into articles
    - _create_digest: Create the digest model
    - _store_digest: Store in database
    """

    def __init__(self, session: Session, graph_client: GraphClient) -> None:
        """Initialise the newsletter service.

        :param session: A SQLAlchemy database session.
        :param graph_client: An authenticated GraphAPI client.
        """
        self._session = session
        self._graph_client = graph_client

    @property
    @abstractmethod
    def sender_email(self) -> str:
        """The sender email address to filter emails by."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name for this newsletter source (for logging)."""
        ...

    @property
    @abstractmethod
    def db_model_class(self) -> type[Base]:
        """The SQLAlchemy model class for this newsletter type."""
        ...

    def _digest_exists(self, email_id: str) -> bool:
        """Check if a digest with this email_id has already been processed.

        :param email_id: The Graph API email ID.
        :returns: True if the digest exists in the database.
        """
        return record_exists_by_field(self._session, self.db_model_class, "email_id", email_id)

    @abstractmethod
    def _parse_html(self, html: str) -> Sequence[ParsedArticleBase]:
        """Parse the email HTML and extract articles.

        :param html: The raw HTML content of the email.
        :returns: A list of parsed articles.
        """
        ...

    @abstractmethod
    def _create_digest(
        self,
        metadata: dict[str, Any],
        articles: Sequence[ParsedArticleBase],
    ) -> ParsedDigestBase:
        """Create a parsed digest model from metadata and articles.

        :param metadata: Email metadata from extract_email_metadata().
        :param articles: Parsed articles from _parse_html().
        :returns: A ParsedDigestBase subclass instance.
        """
        ...

    @abstractmethod
    def _store_digest(self, parsed: ParsedDigestBase) -> tuple[int, int]:
        """Store the parsed digest in the database.

        :param parsed: The parsed digest to store.
        :returns: A tuple of (new_articles_count, duplicate_articles_count).
        """
        ...

    def process_digests(
        self,
        *,
        since: datetime | None = None,
        limit: int = 25,
    ) -> ProcessingResult:
        """Fetch, parse, and store digests from this newsletter source.

        :param since: Only process emails received after this datetime.
        :param limit: Maximum number of emails to process.
        :returns: A ProcessingResult with statistics.
        """
        result = ProcessingResult()

        messages = fetch_emails(
            self._graph_client,
            self.sender_email,
            since=since,
            limit=limit,
        )

        for message in messages:
            try:
                self._process_single_digest(message, result)
            except Exception as e:
                error_msg = f"Failed to process {self.source_name} digest: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)

        logger.info(
            f"{self.source_name} processing complete: {result.digests_processed} digests, "
            f"{result.articles_extracted} articles ({result.articles_new} new, "
            f"{result.articles_duplicate} duplicate)"
        )

        return result

    def _process_single_digest(
        self,
        message: dict[str, Any],
        result: ProcessingResult,
    ) -> None:
        """Process a single email message.

        :param message: The raw email message from Graph API.
        :param result: The ProcessingResult to update.
        """
        metadata = extract_email_metadata(message)
        logger.info(f"Processing {self.source_name} digest: {metadata['subject']}")

        if self._digest_exists(metadata["email_id"]):
            logger.debug(f"{self.source_name} digest already processed: {metadata['email_id']}")
            return

        articles = self._parse_html(metadata["body_html"])
        parsed = self._create_digest(metadata, articles)

        new_count, dup_count = self._store_digest(parsed)

        result.digests_processed += 1
        result.articles_extracted += len(articles)
        result.articles_new += new_count
        result.articles_duplicate += dup_count

        if result.latest_received_at is None or parsed.received_at > result.latest_received_at:
            result.latest_received_at = parsed.received_at
