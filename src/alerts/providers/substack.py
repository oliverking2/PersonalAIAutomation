"""Substack alert provider."""

import logging
import uuid
from itertools import groupby

from sqlalchemy.orm import Session

from src.alerts.enums import AlertType
from src.alerts.models import AlertData, AlertItem
from src.database.substack import get_unsent_substack_posts, mark_substack_post_alerted

logger = logging.getLogger(__name__)


class SubstackAlertProvider:
    """Provider for Substack newsletter alerts.

    Groups all unsent posts into a single alert with items organised
    by publication.
    """

    def __init__(self, session: Session) -> None:
        """Initialise the provider.

        :param session: Database session for queries.
        """
        self._session = session
        self._pending_post_ids: list[uuid.UUID] = []

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.SUBSTACK

    def get_pending_alerts(self) -> list[AlertData]:
        """Get unsent Substack posts grouped by publication.

        Returns a single AlertData containing all unsent posts,
        grouped by publication for display purposes.

        :returns: List containing one AlertData (or empty if no unsent posts).
        """
        unsent = get_unsent_substack_posts(self._session)

        if not unsent:
            logger.info("No unsent Substack posts found")
            return []

        logger.info(f"Found {len(unsent)} unsent Substack posts")

        # Store post IDs for marking as sent later
        self._pending_post_ids = [post.id for post in unsent]

        # Sort by publication name to ensure groupby works correctly
        sorted_posts = sorted(unsent, key=lambda p: p.newsletter.name)

        items: list[AlertItem] = []
        for pub_name, pub_posts in groupby(sorted_posts, key=lambda p: p.newsletter.name):
            posts_list = list(pub_posts)
            for post in posts_list:
                items.append(
                    AlertItem(
                        name=post.title,
                        url=post.url,
                        metadata={
                            "subtitle": post.subtitle or "",
                            "publication": pub_name,
                            "is_paywalled": "true" if post.is_paywalled else "false",
                        },
                    )
                )

        # Use earliest post's timestamp as part of source_id for uniqueness
        earliest = min(unsent, key=lambda p: p.published_at)
        source_id = f"substack-batch-{earliest.published_at.isoformat()}"

        return [
            AlertData(
                alert_type=AlertType.SUBSTACK,
                source_id=source_id,
                title="New Substack Posts",
                items=items,
            )
        ]

    def mark_sent(self, source_id: str) -> None:
        """Mark all pending posts as alerted.

        Since we send all unsent posts as one batch, this marks all
        posts that were included in the pending alert.

        :param source_id: The alert source ID (not used for individual lookups).
        """
        for post_id in self._pending_post_ids:
            mark_substack_post_alerted(self._session, post_id)
            logger.debug(f"Marked Substack post {post_id} as alerted")

        logger.info(f"Marked {len(self._pending_post_ids)} Substack posts as alerted")
        self._pending_post_ids = []
