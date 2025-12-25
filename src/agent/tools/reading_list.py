"""Reading list tool handlers for the AI agent.

These tools are thin wrappers around the API endpoints. All business logic,
validation, and Notion interaction is handled by the API layer.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.agent.api_client import AgentAPIClient
from src.agent.enums import RiskLevel
from src.agent.models import ToolDef
from src.api.notion.reading_list.models import (
    ReadingItemCreateRequest,
    ReadingItemUpdateRequest,
    ReadingQueryRequest,
)
from src.notion.enums import Priority, ReadingCategory, ReadingStatus

logger = logging.getLogger(__name__)


def _get_client() -> AgentAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return AgentAPIClient()


# --- Argument Models ---
# Only define models for tool-specific arguments not covered by API models.


class GetReadingItemArgs(BaseModel):
    """Arguments for getting a reading item by ID."""

    item_id: str = Field(..., min_length=1, description="The Notion page ID of the item")


class UpdateReadingItemArgs(ReadingItemUpdateRequest):
    """Arguments for updating a reading list item (extends API model with item_id)."""

    item_id: str = Field(..., min_length=1, description="The Notion page ID to update")


# --- Tool Handlers ---


def query_reading_list(args: ReadingQueryRequest) -> dict[str, Any]:
    """Query items from the reading list via API.

    :param args: Query arguments with optional filters.
    :returns: Dictionary with 'items' list and 'count'.
    """
    logger.debug(f"Querying reading list: status={args.status}, category={args.category}")

    with _get_client() as client:
        response = client.post(
            "/notion/reading-list/query",
            json=args.model_dump(mode="json", exclude_none=True),
        )

    items = response.get("results", [])
    return {"items": items, "count": len(items)}


def get_reading_item(args: GetReadingItemArgs) -> dict[str, Any]:
    """Get a single reading item by ID via API.

    :param args: Arguments containing the item ID.
    :returns: Dictionary with the reading item details.
    """
    logger.debug(f"Getting reading item: {args.item_id}")

    with _get_client() as client:
        response = client.get(f"/notion/reading-list/{args.item_id}")

    return {"item": response}


def create_reading_item(args: ReadingItemCreateRequest) -> dict[str, Any]:
    """Create a new reading list item via API.

    :param args: Arguments for the new item.
    :returns: Dictionary with the created item details.
    """
    logger.debug(f"Creating reading item: {args.title}")

    with _get_client() as client:
        response = client.post(
            "/notion/reading-list",
            json=args.model_dump(mode="json", exclude_none=True),
        )

    return {"item": response, "created": True}


def update_reading_item(args: UpdateReadingItemArgs) -> dict[str, Any]:
    """Update an existing reading list item via API.

    :param args: Arguments for the update.
    :returns: Dictionary with the updated item details.
    """
    logger.debug(f"Updating reading item: {args.item_id}")

    # Exclude item_id from the payload (it's in the URL)
    payload = args.model_dump(mode="json", exclude_none=True, exclude={"item_id"})

    if not payload:
        return {"error": "No properties to update", "updated": False}

    with _get_client() as client:
        response = client.patch(f"/notion/reading-list/{args.item_id}", json=payload)

    return {"item": response, "updated": True}


# --- Tool Definitions ---


def get_reading_list_tools() -> list[ToolDef]:
    """Get all reading list tool definitions.

    :returns: List of ToolDef instances for reading list operations.
    """
    # Build dynamic descriptions from enums
    status_options = ", ".join(ReadingStatus)
    category_options = ", ".join(ReadingCategory)
    priority_options = ", ".join(Priority)

    return [
        ToolDef(
            name="query_reading_list",
            description=(
                f"Query items from the reading list. Can filter by status "
                f"({status_options}), category ({category_options}), "
                f"and priority ({priority_options})."
            ),
            tags=frozenset({"reading", "query", "list"}),
            risk_level=RiskLevel.SAFE,
            args_model=ReadingQueryRequest,
            handler=query_reading_list,
        ),
        ToolDef(
            name="get_reading_item",
            description=(
                "Get details of a specific reading list item by its ID. "
                "Returns title, status, priority, category, URL, and read date."
            ),
            tags=frozenset({"reading", "get", "item"}),
            risk_level=RiskLevel.SAFE,
            args_model=GetReadingItemArgs,
            handler=get_reading_item,
        ),
        ToolDef(
            name="create_reading_item",
            description=(
                f"Create a new item in the reading list. Requires a title. "
                f"Optional: status ({status_options}), priority ({priority_options}), "
                f"category ({category_options}), and item URL."
            ),
            tags=frozenset({"reading", "create", "item"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=ReadingItemCreateRequest,
            handler=create_reading_item,
        ),
        ToolDef(
            name="update_reading_item",
            description=(
                f"Update an existing reading list item. Requires the item ID. "
                f"Can update title, status ({status_options}), priority ({priority_options}), "
                f"category ({category_options}), URL, or read date."
            ),
            tags=frozenset({"reading", "update", "item"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=UpdateReadingItemArgs,
            handler=update_reading_item,
        ),
    ]
