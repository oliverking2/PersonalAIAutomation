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

    Returns one alert per publication, each containing the unsent posts
    for that publication.
    """

    def __init__(self, session: Session) -> None:
        """Initialise the provider.

        :param session: Database session for queries.
        """
        self._session = session
        # Map source_id -> list of post IDs for that alert
        self._pending_posts_by_source: dict[str, list[uuid.UUID]] = {}

    @property
    def alert_type(self) -> AlertType:
        """The type of alerts this provider generates."""
        return AlertType.SUBSTACK

    def get_pending_alerts(self) -> list[AlertData]:
        """Get unsent Substack posts, one alert per publication.

        :returns: List of AlertData, one per publication with unsent posts.
        """
        unsent = get_unsent_substack_posts(self._session)

        if not unsent:
            logger.info("No unsent Substack posts found")
            return []

        logger.info(f"Found {len(unsent)} unsent Substack posts")

        # Sort by publication name for grouping
        sorted_posts = sorted(unsent, key=lambda p: p.newsletter.name)

        alerts: list[AlertData] = []
        self._pending_posts_by_source = {}

        for pub_name, pub_posts in groupby(sorted_posts, key=lambda p: p.newsletter.name):
            posts_list = list(pub_posts)

            items: list[AlertItem] = []
            for post in posts_list:
                items.append(
                    AlertItem(
                        name=post.title,
                        url=post.url,
                        metadata={
                            "subtitle": post.subtitle or "",
                            "is_paywalled": "true" if post.is_paywalled else "false",
                        },
                    )
                )

            # Use publication name and earliest post timestamp for unique source_id
            earliest = min(posts_list, key=lambda p: p.published_at)
            source_id = f"substack-{pub_name}-{earliest.published_at.isoformat()}"

            # Track which posts belong to this source_id
            self._pending_posts_by_source[source_id] = [p.id for p in posts_list]

            alerts.append(
                AlertData(
                    alert_type=AlertType.SUBSTACK,
                    source_id=source_id,
                    title=pub_name,
                    items=items,
                )
            )

        logger.info(f"Created {len(alerts)} Substack alerts (one per publication)")
        return alerts

    def mark_sent(self, source_id: str) -> None:
        """Mark posts for a specific alert as alerted.

        :param source_id: The alert source ID identifying which publication's posts to mark.
        """
        post_ids = self._pending_posts_by_source.get(source_id, [])

        for post_id in post_ids:
            mark_substack_post_alerted(self._session, post_id)
            logger.debug(f"Marked Substack post {post_id} as alerted")

        logger.info(f"Marked {len(post_ids)} Substack posts as alerted for {source_id}")
