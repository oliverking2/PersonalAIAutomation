"""Database operations for Substack newsletters and posts."""

import logging
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from src.database.substack.models import SubstackNewsletter, SubstackPost

logger = logging.getLogger(__name__)


class SubstackPostData(BaseModel):
    """Data for creating a new Substack post."""

    newsletter_id: uuid.UUID
    post_id: str
    title: str
    subtitle: str | None
    url: str
    is_paywalled: bool = False
    published_at: datetime


def get_or_create_newsletter(
    session: Session,
    url: str,
    name: str,
) -> SubstackNewsletter:
    """Get an existing newsletter or create a new one.

    :param session: The database session.
    :param url: The newsletter URL.
    :param name: The newsletter name.
    :returns: The existing or newly created newsletter.
    """
    newsletter = session.query(SubstackNewsletter).filter(SubstackNewsletter.url == url).first()

    if newsletter is not None:
        # Update name if it changed
        if newsletter.name != name:
            newsletter.name = name
            logger.debug(f"Updated newsletter name for {url} to {name}")
        return newsletter

    newsletter = SubstackNewsletter(url=url, name=name)
    session.add(newsletter)
    session.flush()
    logger.info(f"Created new Substack newsletter: {name} ({url})")
    return newsletter


def ensure_newsletters_exist(
    session: Session,
    publications: list[tuple[str, str]],
) -> dict[str, uuid.UUID]:
    """Ensure all configured publications exist in the database.

    :param session: The database session.
    :param publications: List of (url, name) tuples.
    :returns: Dictionary mapping URL to newsletter ID.
    """
    url_to_id: dict[str, uuid.UUID] = {}
    for url, name in publications:
        newsletter = get_or_create_newsletter(session, url, name)
        url_to_id[url] = newsletter.id
    return url_to_id


def substack_post_exists(session: Session, post_id: str) -> bool:
    """Check if a Substack post has already been stored.

    :param session: The database session.
    :param post_id: The unique post identifier.
    :returns: True if the post exists in the database.
    """
    return session.query(SubstackPost).filter(SubstackPost.post_id == post_id).first() is not None


def create_substack_post(
    session: Session,
    post_data: SubstackPostData,
) -> SubstackPost:
    """Create a new Substack post record.

    :param session: The database session.
    :param post_data: The post data.
    :returns: The created post.
    """
    post = SubstackPost(
        newsletter_id=post_data.newsletter_id,
        post_id=post_data.post_id,
        title=post_data.title,
        subtitle=post_data.subtitle,
        url=post_data.url,
        is_paywalled=post_data.is_paywalled,
        published_at=post_data.published_at,
    )
    session.add(post)
    session.flush()
    logger.debug(f"Created Substack post: {post_data.title}")
    return post


def get_unsent_substack_posts(session: Session) -> list[SubstackPost]:
    """Get all Substack posts that haven't been alerted yet.

    :param session: The database session.
    :returns: List of posts where alerted_at is NULL, ordered by published_at.
    """
    return (
        session.query(SubstackPost)
        .options(joinedload(SubstackPost.newsletter))
        .filter(SubstackPost.alerted_at.is_(None))
        .order_by(SubstackPost.published_at.asc())
        .all()
    )


def mark_substack_post_alerted(session: Session, post_id: uuid.UUID) -> None:
    """Mark a Substack post as alerted.

    :param session: The database session.
    :param post_id: The ID of the post to mark.
    """
    post = session.query(SubstackPost).filter(SubstackPost.id == post_id).one()
    post.alerted_at = datetime.now(UTC)
    session.flush()
    logger.debug(f"Substack post {post_id} marked as alerted")


def get_substack_newsletter_by_url(
    session: Session,
    url: str,
) -> SubstackNewsletter | None:
    """Get a Substack newsletter by its URL.

    :param session: The database session.
    :param url: The newsletter URL.
    :returns: The newsletter or None if not found.
    """
    return session.query(SubstackNewsletter).filter(SubstackNewsletter.url == url).first()
