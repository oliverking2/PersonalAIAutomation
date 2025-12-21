"""Service layer for processing TLDR newsletters."""

import hashlib
import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models.newsletters import Article, Newsletter
from src.database.models.newsletters import NewsletterType as DBNewsletterType
from src.graph.auth import GraphAPI
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


class NewsletterService:
    """Service for processing TLDR newsletters."""

    def __init__(self, session: Session, graph_client: GraphAPI) -> None:
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
            "Processing complete: %d newsletters, %d articles (%d new, %d duplicate)",
            result.newsletters_processed,
            result.articles_extracted,
            result.articles_new,
            result.articles_duplicate,
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

        # Check if already processed
        if self._newsletter_exists(metadata["email_id"]):
            logger.debug("Newsletter already processed: %s", metadata["email_id"])
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
        new_count, dup_count = self._store_newsletter(parsed)

        result.newsletters_processed += 1
        result.articles_extracted += len(articles)
        result.articles_new += new_count
        result.articles_duplicate += dup_count

    def _newsletter_exists(self, email_id: str) -> bool:
        """Check if a newsletter has already been processed.

        :param email_id: The Graph API email ID.
        :returns: True if the newsletter exists in the database.
        """
        return (
            self._session.query(Newsletter).filter(Newsletter.email_id == email_id).first()
            is not None
        )

    def _store_newsletter(self, parsed: ParsedNewsletter) -> tuple[int, int]:
        """Store a parsed newsletter and its articles.

        :param parsed: The parsed newsletter data.
        :returns: A tuple of (new_articles_count, duplicate_articles_count).
        """
        # Map Pydantic enum to SQLAlchemy enum
        db_type = DBNewsletterType(parsed.newsletter_type.value)

        newsletter = Newsletter(
            email_id=parsed.email_id,
            newsletter_type=db_type,
            subject=parsed.subject,
            received_at=parsed.received_at,
            processed_at=datetime.now(UTC),
            article_count=len(parsed.articles),
        )

        self._session.add(newsletter)
        self._session.flush()  # Get the newsletter ID

        new_count = 0
        dup_count = 0

        for article in parsed.articles:
            url_hash = self._compute_url_hash(str(article.url))

            if self._article_exists(url_hash):
                dup_count += 1
                continue

            db_article = Article(
                newsletter_id=newsletter.id,
                title=article.title,
                url=str(article.url),
                url_hash=url_hash,
                description=article.description,
                section=article.section,
                source_publication=article.source_publication,
                position_in_newsletter=article.position,
            )
            self._session.add(db_article)
            new_count += 1

        logger.info(
            "Stored newsletter %s: %d new articles, %d duplicates",
            parsed.email_id[:20],
            new_count,
            dup_count,
        )

        return new_count, dup_count

    def _article_exists(self, url_hash: str) -> bool:
        """Check if an article with this URL already exists.

        :param url_hash: The SHA256 hash of the article URL.
        :returns: True if the article exists in the database.
        """
        return self._session.query(Article).filter(Article.url_hash == url_hash).first() is not None

    @staticmethod
    def _compute_url_hash(url: str) -> str:
        """Compute SHA256 hash of a URL for deduplication.

        :param url: The URL to hash.
        :returns: The hex-encoded SHA256 hash.
        """
        # Normalise URL before hashing
        normalised = url.lower().strip().rstrip("/")
        return hashlib.sha256(normalised.encode()).hexdigest()
