"""Notion API endpoints for managing pages."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.models import PageResponse
from src.api.notion.common.utils import _page_to_response
from src.api.notion.dependencies import get_notion_client
from src.api.notion.pages.models import (
    PageCreateRequest,
    PageUpdateRequest,
)
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError
from src.notion.parser import build_task_properties, parse_page_to_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pages", tags=["Notion - Pages"])


@router.get(
    "/{page_id}",
    response_model=PageResponse,
    summary="Retrieve page",
)
def get_page(
    page_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> PageResponse:
    """Retrieve a single page."""
    logger.debug(f"Retrieving page: {page_id}")
    try:
        data = client.get_page(page_id)
        task = parse_page_to_task(data)
        return _page_to_response(task)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve page: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create page",
)
def create_page(
    request: PageCreateRequest,
    client: NotionClient = Depends(get_notion_client),
) -> PageResponse:
    """Create a new page in a data source."""
    logger.debug(f"Creating page in data source: {request.data_source_id}")
    try:
        properties = build_task_properties(
            task_name=request.task_name,
            status=request.status,
            due_date=request.due_date,
        )
        data = client.create_page(
            data_source_id=request.data_source_id,
            properties=properties,
        )
        task = parse_page_to_task(data)
        return _page_to_response(task)
    except NotionClientError as e:
        logger.exception(f"Failed to create page: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.patch(
    "/{page_id}",
    response_model=PageResponse,
    summary="Update page",
)
def update_page(
    page_id: str,
    request: PageUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
) -> PageResponse:
    """Update a page's properties."""
    logger.debug(f"Updating page: {page_id}")
    try:
        properties = build_task_properties(
            status=request.status,
            due_date=request.due_date,
        )

        if not properties:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties to update. Provide status or due_date.",
            )

        data = client.update_page(page_id=page_id, properties=properties)
        task = parse_page_to_task(data)
        return _page_to_response(task)
    except NotionClientError as e:
        logger.exception(f"Failed to update page: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
