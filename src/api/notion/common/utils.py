"""Common utilities for Notion API."""

from typing import Any

from fastapi import HTTPException, status

from src.api.notion.common.models import PageResponse
from src.notion import NotionTask
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError


def _page_to_response(task: NotionTask) -> PageResponse:
    """Convert a NotionTask to a PageResponse."""
    return PageResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        due_date=task.due_date,
        priority=task.priority,
        url=task.url,
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
