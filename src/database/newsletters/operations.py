"""Database operations for newsletters and articles."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.database.newsletters.models import Article, Newsletter
from src.newsletters.tldr.models import ParsedNewsletter

logger = logging.getLogger(__name__)


def newsletter_exists(session: Session, email_id: str) -> bool:
    """Check if a newsletter has already been processed.

    :param session: The database session.
    :param email_id: The Graph API email ID.
    :returns: True if the newsletter exists in the database.
    """
    return session.query(Newsletter).filter(Newsletter.email_id == email_id).first() is not None


def article_exists(session: Session, url_hash: str) -> bool:
    """Check if an article with this URL hash already exists.

    :param session: The database session.
    :param url_hash: The SHA256 hash of the article URL.
    :returns: True if the article exists in the database.
    """
    return session.query(Article).filter(Article.url_hash == url_hash).first() is not None


def compute_url_hash(url: str) -> str:
    """Compute SHA256 hash of a URL for deduplication.

    :param url: The URL to hash.
    :returns: The hex-encoded SHA256 hash.
    """
    normalised = url.lower().strip().rstrip("/")
    return hashlib.sha256(normalised.encode()).hexdigest()


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
    session.flush()  # Get the newsletter ID

    new_count = 0
    dup_count = 0

    for article in parsed.articles:
        url_hash = compute_url_hash(str(article.url))

        if article_exists(session, url_hash):
            dup_count += 1
            continue

        db_article = Article(
            newsletter_id=newsletter.id,
            title=article.title,
            url=str(article.url),
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


def get_unsent_newsletters(session: Session) -> list[Newsletter]:
    """Get all newsletters that haven't been alerted yet.

    :param session: The database session.
    :returns: List of newsletters where alerted_at is NULL, ordered by received_at.
    """
    return (
        session.query(Newsletter)
        .filter(Newsletter.alerted_at.is_(None))
        .order_by(Newsletter.received_at.asc())
        .all()
    )


def mark_newsletter_alerted(session: Session, newsletter_id: uuid.UUID) -> None:
    """Mark a newsletter as alerted.

    :param session: The database session.
    :param newsletter_id: The ID of the newsletter to mark.
    """
    newsletter = session.query(Newsletter).filter(Newsletter.id == newsletter_id).one()
    newsletter.alerted_at = datetime.now(UTC)
    session.flush()
    logger.debug(f"Newsletter {newsletter_id} marked as alerted")


def get_newsletter_by_id(session: Session, newsletter_id: uuid.UUID) -> Newsletter:
    """Get a newsletter by its ID.

    :param session: The database session.
    :param newsletter_id: The newsletter ID.
    :returns: The newsletter.
    :raises NoResultFound: If no newsletter with this ID exists.
    """
    return session.query(Newsletter).filter(Newsletter.id == newsletter_id).one()
