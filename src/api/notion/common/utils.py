"""Common utilities for Notion API."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any, TypeVar

from fastapi import HTTPException, status
from rapidfuzz import fuzz

from src.api.notion.common.models import PageResponse
from src.notion import NotionTask
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError

T = TypeVar("T")


class FuzzyMatchQuality(StrEnum):
    """Quality indicator for fuzzy name matching results."""

    GOOD = "good"
    WEAK = "weak"


# Minimum token length to include in matching (filters "the", "a", "to", etc.)
MIN_TOKEN_LENGTH = 3

# Fuzzy match threshold for "good" quality
FUZZY_MATCH_THRESHOLD = 60

# Default limit for fuzzy search results
DEFAULT_FUZZY_LIMIT = 5


def _page_to_response(task: NotionTask) -> PageResponse:
    """Convert a NotionTask to a PageResponse."""
    return PageResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        due_date=task.due_date,
        priority=task.priority,
    )


def check_duplicate_name(  # noqa: PLR0913
    client: NotionClient,
    data_source_id: str,
    name_property: str,
    complete_status: str,
    new_name: str,
    exclude_id: str | None = None,
) -> None:
    """Check if a name already exists in open items and raise 409 if duplicate.

    Queries all non-complete items from the data source and checks if the
    given name already exists (case-insensitive comparison).

    :param client: NotionClient instance for API calls.
    :param data_source_id: The data source ID to query.
    :param name_property: The Notion property name for the title field.
    :param complete_status: The status value that indicates completion.
    :param new_name: The name to check for duplicates.
    :param exclude_id: Optional page ID to exclude from the check (for updates).
    :raises HTTPException: 409 Conflict if a duplicate name is found.
    :raises HTTPException: 502 Bad Gateway if Notion API call fails.
    """
    filter_: dict[str, Any] = {
        "property": "Status",
        "status": {"does_not_equal": complete_status},
    }

    try:
        pages = client.query_all_data_source(data_source_id, filter_=filter_)
    except NotionClientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to check for duplicates: {e}",
        ) from e

    new_name_lower = new_name.lower()

    for page in pages:
        page_id = page.get("id", "")

        if exclude_id and page_id == exclude_id:
            continue

        properties = page.get("properties", {})
        title_prop = properties.get(name_property, {})
        title_items = title_prop.get("title", [])
        existing_name = "".join(item.get("plain_text", "") for item in title_items)

        if existing_name.lower() == new_name_lower:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An item with this name already exists: '{existing_name}'",
            )


def filter_by_fuzzy_name(
    items: list[T],
    name_filter: str | None,
    name_getter: Callable[[T], str],
    limit: int = DEFAULT_FUZZY_LIMIT,
) -> tuple[list[T], FuzzyMatchQuality | None]:
    """Filter items by fuzzy name match.

    Uses partial_ratio on the full name string. This is Phase 1 matching.
    Token-based or weighted matching may be added if false positives become common.

    :param items: List of items to filter.
    :param name_filter: Search term (None returns unfiltered results).
    :param name_getter: Callable that extracts the name from an item.
    :param limit: Maximum results to return.
    :returns: Tuple of (filtered items, match quality). Quality is None if unfiltered.
    """
    if not name_filter:
        return items[:limit], None

    # Normalise and strip short tokens from search term
    tokens = name_filter.lower().split()
    filtered_tokens = [t for t in tokens if len(t) >= MIN_TOKEN_LENGTH]
    normalised_filter = " ".join(filtered_tokens) if filtered_tokens else name_filter.lower()

    scored: list[tuple[T, float]] = [
        (item, fuzz.partial_ratio(normalised_filter, name_getter(item).lower())) for item in items
    ]

    # Filter by threshold and sort by score
    matches = [(item, score) for item, score in scored if score >= FUZZY_MATCH_THRESHOLD]
    matches.sort(key=lambda x: x[1], reverse=True)

    if matches:
        return [item for item, _ in matches[:limit]], FuzzyMatchQuality.GOOD

    # No good matches - return top by any score
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in scored[:limit]], FuzzyMatchQuality.WEAK
