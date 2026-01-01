"""Common email fetching utilities for newsletter processing."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from src.graph.client import GraphClient

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_HOURS = 48
DEFAULT_LIMIT = 25


def parse_datetime(dt_string: str) -> datetime:
    """Parse an ISO 8601 datetime string from Graph API.

    :param dt_string: ISO 8601 datetime string (e.g., "2024-01-15T10:30:00Z").
    :returns: A timezone-aware datetime object.
    """
    if dt_string.endswith("Z"):
        dt_string = dt_string[:-1] + "+00:00"
    return datetime.fromisoformat(dt_string)


def extract_email_metadata(message: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant metadata from a Graph API email message.

    :param message: The raw message dict from Graph API.
    :returns: A dict with email_id, subject, sender_name, sender_email,
              received_at, and body_html.
    """
    sender_info = message.get("from", {}).get("emailAddress", {})
    return {
        "email_id": message.get("id", ""),
        "subject": message.get("subject", ""),
        "sender_name": sender_info.get("name", ""),
        "sender_email": sender_info.get("address", ""),
        "received_at": parse_datetime(message.get("receivedDateTime", "")),
        "body_html": message.get("body", {}).get("content", ""),
    }


def fetch_emails(
    graph_client: GraphClient,
    sender_email: str,
    *,
    since: datetime | None = None,
    limit: int = DEFAULT_LIMIT,
    select_fields: str = "id,subject,from,receivedDateTime,body",
) -> list[dict[str, Any]]:
    """Fetch emails from a specific sender via Microsoft Graph API.

    :param graph_client: An authenticated GraphClient instance.
    :param sender_email: The sender email address to filter by.
    :param since: Only fetch emails received after this datetime.
    :param limit: Maximum number of emails to fetch.
    :param select_fields: Comma-separated list of fields to request.
    :returns: A list of email message dicts from the Graph API.
    """
    if since is None:
        since = datetime.now(UTC) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)

    since_iso = since.isoformat()

    logger.info(f"Fetching emails from {sender_email} since {since_iso} (limit={limit})")

    # receivedDateTime must come first for Graph API to use its index efficiently
    filter_query = (
        f"receivedDateTime ge {since_iso} and from/emailAddress/address eq '{sender_email}'"
    )

    response = graph_client.get(
        "mailFolders/Inbox/messages",
        params={
            "$filter": filter_query,
            "$select": select_fields,
            "$top": str(limit),
            "$orderby": "receivedDateTime desc",
        },
    )
    response.raise_for_status()

    messages = response.json().get("value", [])
    logger.info(f"Fetched {len(messages)} email(s) from {sender_email}")

    return messages
