"""Database operations for Medium digests and articles."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database.base import compute_url_hash, record_exists_by_field
from src.database.medium.models import MediumArticle, MediumDigest

if TYPE_CHECKING:
    from src.newsletters.medium.models import ParsedMediumDigest

logger = logging.getLogger(__name__)


def create_digest(
    session: Session,
    parsed: ParsedMediumDigest,
) -> tuple[MediumDigest, int, int]:
    """Store a parsed Medium digest and its articles.

    :param session: The database session.
    :param parsed: The parsed digest data.
    :returns: A tuple of (digest, new_articles_count, duplicate_articles_count).
    """
    digest = MediumDigest(
        email_id=parsed.email_id,
        subject=parsed.subject,
        received_at=parsed.received_at,
        processed_at=datetime.now(UTC),
    )

    session.add(digest)
    session.flush()

    new_count = 0
    dup_count = 0

    for article in parsed.articles:
        url_hash = compute_url_hash(str(article.url))

        if record_exists_by_field(session, MediumArticle, "url_hash", url_hash):
            dup_count += 1
            continue

        db_article = MediumArticle(
            digest_id=digest.id,
            title=article.title,
            url=str(article.url),
            url_hash=url_hash,
            description=article.description,
            read_time_minutes=article.read_time_minutes,
        )
        session.add(db_article)
        new_count += 1

    logger.info(
        f"Stored Medium digest {parsed.email_id[:20]}: {new_count} new articles, "
        f"{dup_count} duplicates"
    )

    return digest, new_count, dup_count
