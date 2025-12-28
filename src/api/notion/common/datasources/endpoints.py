"""Notion API endpoints for data sources."""

import logging
import time

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
    start = time.perf_counter()
    logger.info("List data source templates")
    try:
        data = client.list_data_source_templates()
        templates = data.get("results", [])

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"List data source templates complete: count={len(templates)}, elapsed={elapsed_ms:.0f}ms"
        )

        return TemplatesResponse(templates=templates)
    except NotionClientError as e:
        logger.exception(f"Failed to list templates: error={e}")
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
    start = time.perf_counter()
    logger.info(f"Get data source: id={data_source_id}")
    try:
        data = client.get_data_source(data_source_id)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Get data source complete: id={data_source_id}, "
            f"properties={len(data.get('properties', {}))}, elapsed={elapsed_ms:.0f}ms"
        )

        return DataSourceResponse(
            id=data["id"],
            database_id=data.get("database_id", ""),
            properties=data.get("properties", {}),
        )
    except NotionClientError as e:
        logger.exception(f"Failed to get data source: id={data_source_id}, error={e}")
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
    start = time.perf_counter()
    has_filter = request.filter is not None
    has_sorts = request.sorts is not None
    logger.info(
        f"Query data source: id={data_source_id}, has_filter={has_filter}, has_sorts={has_sorts}"
    )
    try:
        pages_data = client.query_all_data_source(
            data_source_id,
            filter_=request.filter,
            sorts=request.sorts,
        )
        pages = [_page_to_response(parse_page_to_task(page)) for page in pages_data]

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Query data source complete: id={data_source_id}, "
            f"found={len(pages)}, elapsed={elapsed_ms:.0f}ms"
        )

        return QueryResponse(results=pages)
    except NotionClientError as e:
        logger.exception(f"Failed to query data source: id={data_source_id}, error={e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
