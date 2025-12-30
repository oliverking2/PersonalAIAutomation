"""Service layer for processing Substack newsletters."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil import parser as dateparser
from sqlalchemy.orm import Session

from src.database.substack import (
    SubstackPostData,
    create_substack_post,
    ensure_newsletters_exist,
    substack_post_exists,
)
from src.newsletters.substack.models import SubstackProcessingResult
from src.substack import Newsletter, Post, SubstackClient, User

logger = logging.getLogger(__name__)


@dataclass
class PublicationContext:
    """Context for processing a single publication."""

    url: str
    name: str
    newsletter_id: uuid.UUID
    since: datetime | None
    limit: int


class SubstackService:
    """Service for fetching and storing Substack posts."""

    def __init__(
        self,
        session: Session,
        client: SubstackClient | None = None,
    ) -> None:
        """Initialise the Substack service.

        :param session: A SQLAlchemy database session.
        :param client: An optional SubstackClient (uses default if not provided).
        """
        self._session = session
        self._client = client or SubstackClient(rate_limit=True)

        self._substack_user = User("oliverking804615")
        self._substack_publications = [
            (sub["domain"], sub["publication_name"])
            for sub in self._substack_user.get_subscriptions()
        ]

    def process_publications(
        self,
        *,
        since: datetime | None = None,
        limit_per_publication: int = 10,
    ) -> SubstackProcessingResult:
        """Fetch and store new posts from all configured publications.

        :param since: Only store posts published after this datetime.
        :param limit_per_publication: Maximum posts to fetch per publication.
        :returns: Processing result with statistics.
        """
        result = SubstackProcessingResult()

        # Ensure all newsletters exist in the database
        url_to_id = ensure_newsletters_exist(self._session, self._substack_publications)

        for pub_url, pub_name in self._substack_publications:
            try:
                context = PublicationContext(
                    url=pub_url,
                    name=pub_name,
                    newsletter_id=url_to_id[pub_url],
                    since=since,
                    limit=limit_per_publication,
                )
                self._process_publication(context, result)
            except Exception as e:
                error_msg = f"Failed to process {pub_name}: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)

        logger.info(
            f"Substack processing complete: {result.posts_processed} processed, "
            f"{result.posts_new} new, {result.posts_duplicate} duplicate"
        )

        return result

    def _process_publication(
        self,
        ctx: PublicationContext,
        result: SubstackProcessingResult,
    ) -> None:
        """Process a single publication.

        :param ctx: Context with publication details.
        :param result: The result object to update.
        """
        logger.info(f"Processing Substack publication: {ctx.name} ({ctx.url})")

        newsletter = Newsletter(ctx.url, client=self._client)
        posts = newsletter.get_posts(sorting="new", limit=ctx.limit)

        for post in posts:
            try:
                self._process_post(post, ctx.newsletter_id, ctx.since, result)
            except Exception as e:
                error_msg = f"Failed to process post {post.url}: {e}"
                logger.exception(error_msg)
                result.errors.append(error_msg)

    def _process_post(
        self,
        post: Post,
        newsletter_id: uuid.UUID,
        since: datetime | None,
        result: SubstackProcessingResult,
    ) -> None:
        """Process a single post.

        :param post: The Post object.
        :param newsletter_id: The database ID of the newsletter.
        :param since: Only store posts published after this datetime.
        :param result: The result object to update.
        """
        metadata = post.get_metadata()

        # Parse the published date
        published_at = self._parse_published_at(metadata)

        # Skip if older than watermark
        if since and published_at <= since:
            logger.debug(f"Skipping post (before watermark): {metadata.get('title')}")
            return

        # Generate unique post ID
        post_id = self._generate_post_id(metadata)

        # Skip duplicates
        if substack_post_exists(self._session, post_id):
            result.posts_duplicate += 1
            logger.debug(f"Skipping duplicate post: {metadata.get('title')}")
            return

        # Check if post is paywalled
        is_paywalled = metadata.get("audience") == "only_paid"

        post_data = SubstackPostData(
            newsletter_id=newsletter_id,
            post_id=post_id,
            title=metadata["title"],
            subtitle=metadata.get("subtitle"),
            url=metadata.get("canonical_url", post.url),
            is_paywalled=is_paywalled,
            published_at=published_at,
        )

        create_substack_post(self._session, post_data)
        result.posts_new += 1
        result.posts_processed += 1

        # Track latest for watermark
        if result.latest_published_at is None or published_at > result.latest_published_at:
            result.latest_published_at = published_at

        logger.debug(f"Stored new post: {metadata['title']}")

    def _parse_published_at(self, metadata: dict[str, object]) -> datetime:
        """Parse published_at from post metadata.

        Tries multiple field names since Substack API can return dates in
        different fields.

        :param metadata: The post metadata.
        :returns: A timezone-aware datetime.
        :raises ValueError: If no valid date field is found.
        """
        # Try different date field names
        date_fields = ["post_date", "published_at", "created_at"]

        for field in date_fields:
            value = metadata.get(field)
            if value:
                if isinstance(value, datetime):
                    if value.tzinfo is None:
                        return value.replace(tzinfo=UTC)
                    return value
                if isinstance(value, str):
                    parsed = dateparser.parse(value)
                    if parsed.tzinfo is None:
                        return parsed.replace(tzinfo=UTC)
                    return parsed

        msg = f"No valid date field found in metadata: {metadata.keys()}"
        raise ValueError(msg)

    def _generate_post_id(self, metadata: dict[str, object]) -> str:
        """Generate unique post ID from metadata.

        Uses the API ID if available, otherwise falls back to canonical URL.

        :param metadata: The post metadata.
        :returns: A unique string identifier.
        """
        # Prefer the Substack post ID
        if "id" in metadata:
            return str(metadata["id"])

        # Fall back to canonical URL
        if "canonical_url" in metadata:
            return str(metadata["canonical_url"])

        # Last resort: use the slug
        if "slug" in metadata:
            return str(metadata["slug"])

        msg = f"Cannot generate post ID from metadata: {metadata.keys()}"
        raise ValueError(msg)
