"""Fetcher for TLDR newsletters via Microsoft Graph API."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from src.graph.auth import GraphAPI

logger = logging.getLogger(__name__)

TLDR_SENDER_EMAIL = "dan@tldrnewsletter.com"
DEFAULT_LOOKBACK_HOURS = 48
DEFAULT_LIMIT = 25


def fetch_tldr_newsletters(
    graph_client: GraphAPI,
    *,
    since: datetime | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Fetch TLDR newsletter emails from Outlook inbox.

    :param graph_client: An authenticated GraphAPI client.
    :param since: Only fetch emails received after this datetime.
        Defaults to 48 hours ago.
    :param limit: Maximum number of emails to fetch.
    :returns: A list of email message dictionaries from the Graph API.
    :raises requests.RequestException: If the API request fails.
    """
    if since is None:
        since = datetime.now(UTC) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)

    filter_expr = (
        f"receivedDateTime ge {since.isoformat()} "
        f"and from/emailAddress/address eq '{TLDR_SENDER_EMAIL}'"
    )

    params = {
        "$filter": filter_expr,
        "$select": "id,subject,from,receivedDateTime,body",
        "$orderby": "receivedDateTime desc",
        "$top": str(limit),
    }

    logger.info(f"Fetching TLDR newsletters since {since.isoformat()} (limit={limit})")

    response = graph_client.get(
        endpoint="mailFolders/Inbox/messages",
        params=params,
    )
    response.raise_for_status()

    data = response.json()
    messages = data.get("value", [])

    logger.info(f"Fetched {len(messages)} TLDR newsletter(s)")
    return messages


def extract_email_metadata(message: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant metadata from a Graph API email message.

    :param message: The raw email message from Graph API.
    :returns: A dictionary with extracted metadata.
    """
    sender_info = message.get("from", {}).get("emailAddress", {})

    return {
        "email_id": message.get("id", ""),
        "subject": message.get("subject", ""),
        "sender_name": sender_info.get("name", ""),
        "sender_email": sender_info.get("address", ""),
        "received_at": _parse_datetime(message.get("receivedDateTime", "")),
        "body_html": message.get("body", {}).get("content", ""),
    }


def _parse_datetime(dt_string: str) -> datetime:
    """Parse an ISO 8601 datetime string from Graph API.

    :param dt_string: The datetime string to parse.
    :returns: A timezone-aware datetime object.
    """
    # Graph API returns datetime in ISO 8601 format
    # Handle both 'Z' suffix and offset formats
    if dt_string.endswith("Z"):
        dt_string = dt_string[:-1] + "+00:00"

    return datetime.fromisoformat(dt_string)
