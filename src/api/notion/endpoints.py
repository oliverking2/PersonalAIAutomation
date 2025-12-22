"""Notion API endpoints for managing databases, data sources, and pages."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import verify_token
from src.api.notion.models import (
    DatabaseResponse,
    DataSourceResponse,
    PageCreateRequest,
    PageResponse,
    PageUpdateRequest,
    QueryRequest,
    QueryResponse,
    TemplatesResponse,
)
from src.notion.client import NotionClient
from src.notion.exceptions import NotionClientError
from src.notion.models import NotionTask
from src.notion.parser import (
    build_create_properties,
    build_update_properties,
    parse_page_to_task,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notion", tags=["notion"], dependencies=[Depends(verify_token)])


def get_notion_client() -> NotionClient:
    """Create a NotionClient instance.

    :returns: Configured NotionClient.
    :raises HTTPException: If client initialisation fails.
    """
    try:
        return NotionClient()
    except ValueError as e:
        logger.error(f"Failed to initialise Notion client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notion integration not configured",
        ) from e


# Database endpoints


@router.get(
    "/databases/{database_id}",
    response_model=DatabaseResponse,
    summary="Retrieve database",
    description="Get database structure and property schema.",
)
def get_database(
    database_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> DatabaseResponse:
    """Retrieve database structure and properties.

    :param database_id: Notion database ID.
    :returns: Database response with properties schema.
    :raises HTTPException: If the Notion API request fails.
    """
    logger.debug(f"Retrieving database: {database_id}")
    try:
        data = client.get_database(database_id)
        title_items = data.get("title", [])
        title = "".join(item.get("plain_text", "") for item in title_items)
        return DatabaseResponse(
            id=data["id"],
            title=title,
            properties=data.get("properties", {}),
        )
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve database: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


# Data source endpoints


@router.get(
    "/data-sources/templates",
    response_model=TemplatesResponse,
    summary="List data source templates",
    description="Get available templates for creating data sources.",
)
def list_templates(
    client: NotionClient = Depends(get_notion_client),
) -> TemplatesResponse:
    """List available data source templates.

    :returns: Response with list of templates.
    :raises HTTPException: If the Notion API request fails.
    """
    logger.debug("Listing data source templates")
    try:
        data = client.list_data_source_templates()
        return TemplatesResponse(
            templates=data.get("results", []),
        )
    except NotionClientError as e:
        logger.exception(f"Failed to list templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.get(
    "/data-sources/{data_source_id}",
    response_model=DataSourceResponse,
    summary="Retrieve data source",
    description="Get data source configuration and properties.",
)
def get_data_source(
    data_source_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> DataSourceResponse:
    """Retrieve data source configuration.

    :param data_source_id: Notion data source ID.
    :returns: Data source response with configuration.
    :raises HTTPException: If the Notion API request fails.
    """
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.post(
    "/data-sources/{data_source_id}/query",
    response_model=QueryResponse,
    summary="Query data source",
    description="Query all pages from a data source with optional filters and sorts. "
    "Pagination is handled automatically - all matching results are returned.",
)
def query_data_source(
    data_source_id: str,
    request: QueryRequest,
    client: NotionClient = Depends(get_notion_client),
) -> QueryResponse:
    """Query all pages from a data source.

    Pagination is handled automatically - all matching results are returned
    in a single response.

    :param data_source_id: Notion data source ID.
    :param request: Query parameters including filters and sorts.
    :returns: Query response with all matching pages.
    :raises HTTPException: If the Notion API request fails.
    """
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


# Page endpoints


@router.get(
    "/pages/{page_id}",
    response_model=PageResponse,
    summary="Retrieve page",
    description="Get a single page with its properties.",
)
def get_page(
    page_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> PageResponse:
    """Retrieve a single page.

    :param page_id: Notion page ID.
    :returns: Page response with properties.
    :raises HTTPException: If the Notion API request fails.
    """
    logger.debug(f"Retrieving page: {page_id}")
    try:
        data = client.get_page(page_id)
        task = parse_page_to_task(data)
        return _page_to_response(task)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve page: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.post(
    "/pages",
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create page",
    description="Create a new page in a data source.",
)
def create_page(
    request: PageCreateRequest,
    client: NotionClient = Depends(get_notion_client),
) -> PageResponse:
    """Create a new page in a data source.

    :param request: Page creation parameters.
    :returns: Created page response.
    :raises HTTPException: If the Notion API request fails.
    """
    logger.debug(f"Creating page in data source: {request.data_source_id}")
    try:
        properties = build_create_properties(
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.patch(
    "/pages/{page_id}",
    response_model=PageResponse,
    summary="Update page",
    description="Update a page's status or due date.",
)
def update_page(
    page_id: str,
    request: PageUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
) -> PageResponse:
    """Update a page's properties.

    :param page_id: Notion page ID.
    :param request: Properties to update.
    :returns: Updated page response.
    :raises HTTPException: If the Notion API request fails.
    """
    logger.debug(f"Updating page: {page_id}")
    try:
        properties = build_update_properties(
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


def _page_to_response(task: NotionTask) -> PageResponse:
    """Convert a NotionTask to a PageResponse.

    :param task: Parsed Notion task.
    :returns: API response model.
    """
    return PageResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        due_date=task.due_date,
        priority=task.priority,
        url=task.url,
    )
