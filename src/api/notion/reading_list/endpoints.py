"""Notion API endpoints for managing reading list."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.utils import check_duplicate_name
from src.api.notion.dependencies import get_notion_client, get_reading_data_source_id
from src.api.notion.reading_list.models import (
    ReadingItemCreateRequest,
    ReadingItemResponse,
    ReadingItemUpdateRequest,
    ReadingQueryRequest,
    ReadingQueryResponse,
)
from src.notion.client import NotionClient
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
    """Query all items from the configured reading list."""
    logger.debug("Querying reading list")
    try:
        pages_data = client.query_all_data_source(
            data_source_id,
            filter_=request.filter,
            sorts=request.sorts,
        )
        items = [_reading_to_response(parse_page_to_reading_item(page)) for page in pages_data]
        return ReadingQueryResponse(results=items)
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
        return _reading_to_response(item)
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
        return _reading_to_response(item)
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

        if not properties:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties to update.",
            )

        data = client.update_page(page_id=item_id, properties=properties)
        item = parse_page_to_reading_item(data)
        return _reading_to_response(item)
    except NotionClientError as e:
        logger.exception(f"Failed to update reading item: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _reading_to_response(item: NotionReadingItem) -> ReadingItemResponse:
    """Convert a NotionReadingItem to a ReadingItemResponse."""
    return ReadingItemResponse(
        id=item.id,
        title=item.title,
        status=item.status,
        priority=item.priority,
        category=item.category,
        item_url=item.item_url,
        read_date=item.read_date,
        url=item.url,
    )
