"""Notion API endpoints for managing reading list."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.utils import check_duplicate_name, filter_by_fuzzy_name
from src.api.notion.dependencies import get_notion_client, get_reading_data_source_id
from src.api.notion.reading_list.models import (
    ReadingItemCreateRequest,
    ReadingItemResponse,
    ReadingItemUpdateRequest,
    ReadingQueryRequest,
    ReadingQueryResponse,
)
from src.notion.blocks import blocks_to_markdown, markdown_to_blocks
from src.notion.client import NotionClient
from src.notion.enums import ReadingStatus
from src.notion.exceptions import NotionClientError
from src.notion.models import NotionReadingItem
from src.notion.parser import build_reading_properties, parse_page_to_reading_item

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reading-list", tags=["Notion - Reading List"])


@router.post(
    "/query",
    response_model=ReadingQueryResponse,
    summary="Query reading list",
)
def query_reading(
    request: ReadingQueryRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_reading_data_source_id),
) -> ReadingQueryResponse:
    """Query items from the configured reading list.

    By default, completed items are excluded unless include_completed=True.
    If name_filter is provided, results are fuzzy-matched and limited to top 5.
    """
    logger.debug("Querying reading list")
    try:
        filter_ = _build_reading_filter(request)
        # Default sort by last edited time descending (latest first)
        sorts = [{"timestamp": "last_edited_time", "direction": "descending"}]
        pages_data = client.query_all_data_source(data_source_id, filter_=filter_, sorts=sorts)

        # Parse all pages to reading item responses
        items = [_reading_to_response(parse_page_to_reading_item(page)) for page in pages_data]

        # Apply fuzzy name filter if provided
        filtered_items, fuzzy_quality = filter_by_fuzzy_name(
            items=items,
            name_filter=request.name_filter,
            name_getter=lambda i: i.title,
            limit=request.limit if not request.name_filter else 5,
        )

        return ReadingQueryResponse(
            results=filtered_items,
            fuzzy_match_quality=fuzzy_quality,
            excluded_completed=not request.include_completed,
        )
    except NotionClientError as e:
        logger.exception(f"Failed to query reading list: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/{item_id}",
    response_model=ReadingItemResponse,
    summary="Get reading item",
)
def get_reading_item(
    item_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> ReadingItemResponse:
    """Retrieve a single reading item."""
    logger.debug(f"Retrieving reading item: {item_id}")
    try:
        data = client.get_page(item_id)
        item = parse_page_to_reading_item(data)

        # Fetch page content
        blocks = client.get_page_content(item_id)
        content = blocks_to_markdown(blocks) if blocks else None

        return _reading_to_response(item, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve reading item: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=ReadingItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create reading item",
)
def create_reading_item(
    request: ReadingItemCreateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_reading_data_source_id),
) -> ReadingItemResponse:
    """Create a new item in the reading list."""
    logger.debug("Creating reading item")

    check_duplicate_name(
        client=client,
        data_source_id=data_source_id,
        name_property="Title",
        complete_status="Completed",
        new_name=request.title,
    )

    try:
        properties = build_reading_properties(
            title=request.title,
            status=request.status,
            priority=request.priority,
            category=request.category,
            item_url=request.item_url,
            read_date=request.read_date,
        )
        data = client.create_page(
            data_source_id=data_source_id,
            properties=properties,
        )
        item = parse_page_to_reading_item(data)

        # Append content if provided
        if request.content:
            blocks = markdown_to_blocks(request.content)
            client.append_page_content(item.id, blocks)

        return _reading_to_response(item, content=request.content)
    except NotionClientError as e:
        logger.exception(f"Failed to create reading item: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.patch(
    "/{item_id}",
    response_model=ReadingItemResponse,
    summary="Update reading item",
)
def update_reading_item(
    item_id: str,
    request: ReadingItemUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_reading_data_source_id),
) -> ReadingItemResponse:
    """Update a reading item's properties."""
    logger.debug(f"Updating reading item: {item_id}")

    if request.title is not None:
        check_duplicate_name(
            client=client,
            data_source_id=data_source_id,
            name_property="Title",
            complete_status="Completed",
            new_name=request.title,
            exclude_id=item_id,
        )

    try:
        properties = build_reading_properties(
            title=request.title,
            status=request.status,
            priority=request.priority,
            category=request.category,
            item_url=request.item_url,
            read_date=request.read_date,
        )

        if not properties and request.content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties or content to update.",
            )

        # Update properties if any
        if properties:
            data = client.update_page(page_id=item_id, properties=properties)
            item = parse_page_to_reading_item(data)
        else:
            # Content-only update - fetch current item
            data = client.get_page(item_id)
            item = parse_page_to_reading_item(data)

        # Replace content if provided
        content: str | None
        if request.content is not None:
            new_blocks = markdown_to_blocks(request.content)
            client.replace_page_content(item_id, new_blocks)
            content = request.content
        else:
            # Fetch existing content
            blocks = client.get_page_content(item_id)
            content = blocks_to_markdown(blocks) if blocks else None

        return _reading_to_response(item, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to update reading item: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _build_reading_filter(request: ReadingQueryRequest) -> dict[str, object] | None:
    """Build Notion filter from structured query request.

    :param request: Query request with filter fields.
    :returns: Notion filter dictionary or None if no filters.
    """
    conditions: list[dict[str, object]] = []

    # Exclude Completed items by default unless include_completed is True
    if not request.include_completed:
        conditions.append(
            {"property": "Status", "status": {"does_not_equal": ReadingStatus.COMPLETED.value}}
        )

    if request.status:
        conditions.append({"property": "Status", "status": {"equals": request.status.value}})

    if request.category:
        conditions.append({"property": "Category", "select": {"equals": request.category.value}})

    if request.priority:
        conditions.append({"property": "Priority", "select": {"equals": request.priority.value}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def _reading_to_response(
    item: NotionReadingItem, content: str | None = None
) -> ReadingItemResponse:
    """Convert a NotionReadingItem to a ReadingItemResponse.

    :param item: The NotionReadingItem to convert.
    :param content: Optional markdown content for the page.
    :returns: ReadingItemResponse with all fields.
    """
    return ReadingItemResponse(
        id=item.id,
        title=item.title,
        status=item.status,
        priority=item.priority,
        category=item.category,
        item_url=item.item_url,
        read_date=item.read_date,
        url=item.url,
        content=content,
    )
