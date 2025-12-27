"""Notion API endpoints for managing pages."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.models import PageResponse
from src.api.notion.common.pages.models import (
    PageContentRequest,
    PageContentResponse,
    PageCreateRequest,
    PageUpdateRequest,
)
from src.api.notion.common.utils import _page_to_response
from src.api.notion.dependencies import get_notion_client
from src.notion.blocks import blocks_to_markdown, markdown_to_blocks
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


@router.get(
    "/{page_id}/content",
    response_model=PageContentResponse,
    summary="Get page content",
)
def get_page_content(
    page_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> PageContentResponse:
    """Retrieve page content as blocks and markdown."""
    logger.debug(f"Retrieving content for page: {page_id}")
    try:
        blocks = client.get_page_content(page_id)
        markdown = blocks_to_markdown(blocks)
        return PageContentResponse(blocks=blocks, markdown=markdown)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve page content: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.put(
    "/{page_id}/content",
    response_model=PageContentResponse,
    summary="Replace page content",
)
def replace_page_content(
    page_id: str,
    request: PageContentRequest,
    client: NotionClient = Depends(get_notion_client),
) -> PageContentResponse:
    """Replace all page content with new markdown content."""
    logger.debug(f"Replacing content for page: {page_id}")
    try:
        blocks = markdown_to_blocks(request.markdown)
        client.replace_page_content(page_id, blocks)
        return PageContentResponse(blocks=blocks, markdown=request.markdown)
    except NotionClientError as e:
        logger.exception(f"Failed to replace page content: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "/{page_id}/content",
    response_model=PageContentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append to page content",
)
def append_page_content(
    page_id: str,
    request: PageContentRequest,
    client: NotionClient = Depends(get_notion_client),
) -> PageContentResponse:
    """Append markdown content to existing page content."""
    logger.debug(f"Appending content to page: {page_id}")
    try:
        new_blocks = markdown_to_blocks(request.markdown)
        client.append_page_content(page_id, new_blocks)

        # Return the full content after append
        all_blocks = client.get_page_content(page_id)
        markdown = blocks_to_markdown(all_blocks)
        return PageContentResponse(blocks=all_blocks, markdown=markdown)
    except NotionClientError as e:
        logger.exception(f"Failed to append page content: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
