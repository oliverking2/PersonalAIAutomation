"""Fetcher for Medium Daily Digests via Microsoft Graph API."""

from datetime import datetime
from typing import Any

from src.graph.client import GraphClient
from src.newsletters.base.fetcher import (
    DEFAULT_LIMIT,
    fetch_emails,
)

MEDIUM_SENDER_EMAIL = "noreply@medium.com"


def fetch_medium_digests(
    graph_client: GraphClient,
    *,
    since: datetime | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch Medium Daily Digest emails from Outlook inbox.

    :param graph_client: An authenticated GraphAPI client.
    :param since: Only fetch emails received after this datetime.
        Defaults to 48 hours ago.
    :param limit: Maximum number of emails to fetch.
    :returns: A list of email message dictionaries from the Graph API.
    """
    return fetch_emails(
        graph_client,
        MEDIUM_SENDER_EMAIL,
        since=since,
        limit=limit,
    )
