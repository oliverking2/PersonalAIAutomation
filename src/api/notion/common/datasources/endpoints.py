"""Notion API endpoints for data sources."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.datasources.models import (
    DataSourceResponse,
    QueryRequest,
    TemplatesResponse,
)
from src.api.notion.common.models import QueryResponse
from src.api.notion.common.utils import _page_to_response
from src.api.notion.dependencies import get_notion_client
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError
from src.notion.parser import parse_page_to_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-sources", tags=["Notion - Data Sources"])


@router.get(
    "/templates",
    response_model=TemplatesResponse,
    summary="List data source templates",
)
def list_templates(
    client: NotionClient = Depends(get_notion_client),
) -> TemplatesResponse:
    """List available data source templates."""
    logger.debug("Listing data source templates")
    try:
        data = client.list_data_source_templates()
        return TemplatesResponse(templates=data.get("results", []))
    except NotionClientError as e:
        logger.exception(f"Failed to list templates: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/{data_source_id}",
    response_model=DataSourceResponse,
    summary="Retrieve data source",
)
def get_data_source(
    data_source_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> DataSourceResponse:
    """Retrieve data source configuration."""
    logger.debug(f"Retrieving data source: {data_source_id}")
    try:
        data = client.get_data_source(data_source_id)
        return DataSourceResponse(
            id=data["id"],
            database_id=data.get("database_id", ""),
            properties=data.get("properties", {}),
        )
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve data source: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "/{data_source_id}/query",
    response_model=QueryResponse,
    summary="Query data source",
)
def query_data_source(
    data_source_id: str,
    request: QueryRequest,
    client: NotionClient = Depends(get_notion_client),
) -> QueryResponse:
    """Query all pages from a data source with automatic pagination."""
    logger.debug(f"Querying all pages from data source: {data_source_id}")
    try:
        pages_data = client.query_all_data_source(
            data_source_id,
            filter_=request.filter,
            sorts=request.sorts,
        )
        pages = [_page_to_response(parse_page_to_task(page)) for page in pages_data]
        return QueryResponse(results=pages)
    except NotionClientError as e:
        logger.exception(f"Failed to query data source: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
