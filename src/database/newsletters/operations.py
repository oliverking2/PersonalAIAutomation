"""Database operations for newsletters and articles."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import requests
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.base import compute_url_hash, record_exists_by_field
from src.database.newsletters.models import Article, Newsletter

if TYPE_CHECKING:
    from src.newsletters.tldr.models import ParsedNewsletter

logger = logging.getLogger(__name__)


def create_newsletter(
    session: Session,
    parsed: ParsedNewsletter,
) -> tuple[Newsletter, int, int]:
    """Store a parsed newsletter and its articles.

    :param session: The database session.
    :param parsed: The parsed newsletter data.
    :returns: A tuple of (newsletter, new_articles_count, duplicate_articles_count).
    """
    newsletter = Newsletter(
        email_id=parsed.email_id,
        newsletter_type=parsed.newsletter_type,
        subject=parsed.subject,
        received_at=parsed.received_at,
        processed_at=datetime.now(UTC),
    )

    session.add(newsletter)
    session.flush()

    new_count = 0
    dup_count = 0

    for article in parsed.articles:
        url_hash = compute_url_hash(str(article.url))

        if record_exists_by_field(session, Article, "url_hash", url_hash):
            dup_count += 1
            continue

        db_article = Article(
            newsletter_id=newsletter.id,
            title=article.title,
            url=str(article.url),
            url_parsed=str(article.url_parsed),
            url_hash=url_hash,
            description=article.description,
        )
        session.add(db_article)
        new_count += 1

    logger.info(
        f"Stored newsletter {parsed.email_id[:20]}: {new_count} new articles, "
        f"{dup_count} duplicates"
    )

    return newsletter, new_count, dup_count


class BackfillResult(BaseModel):
    """Result of backfilling article URLs."""

    articles_updated: int = 0
    articles_failed: int = 0
    errors: list[str] = Field(default_factory=list)


def backfill_article_urls(session: Session) -> BackfillResult:
    """Backfill url_parsed for articles that don't have it set.

    Fetches the final destination URL for each article by following redirects.

    :param session: The database session.
    :returns: A BackfillResult with statistics about the operation.
    """
    # Import here to avoid circular dependency
    from src.newsletters.tldr.parser import _unpack_href  # noqa: PLC0415

    result = BackfillResult()

    articles = session.query(Article).filter(Article.url_parsed.is_(None)).all()

    logger.info(f"Found {len(articles)} articles to backfill")

    for article in articles:
        try:
            parsed_url = _unpack_href(article.url)
            article.url_parsed = parsed_url
            result.articles_updated += 1
            logger.debug(f"Backfilled article {article.id}: {article.url} -> {parsed_url}")
        except requests.RequestException as e:
            error_msg = f"Failed to unpack URL for article {article.id} ({article.url}): {e}"
            logger.warning(error_msg)
            result.errors.append(error_msg)
            result.articles_failed += 1

    session.flush()

    logger.info(
        f"Backfill complete: {result.articles_updated} updated, {result.articles_failed} failed"
    )

    return result
