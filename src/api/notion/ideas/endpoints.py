"""Notion API endpoints for managing ideas."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.models import BulkCreateFailure
from src.api.notion.common.utils import check_duplicate_name, filter_by_fuzzy_name
from src.api.notion.dependencies import get_ideas_data_source_id, get_notion_client
from src.api.notion.ideas.models import (
    IdeaBulkCreateResponse,
    IdeaCreateRequest,
    IdeaQueryRequest,
    IdeaQueryResponse,
    IdeaResponse,
    IdeaUpdateRequest,
)
from src.notion.blocks import blocks_to_markdown, markdown_to_blocks
from src.notion.client import NotionClient
from src.notion.enums import IdeaStatus
from src.notion.exceptions import NotionClientError
from src.notion.models import NotionIdea
from src.notion.parser import build_idea_properties, parse_page_to_idea

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas", tags=["Notion - Ideas"])


@router.post(
    "/query",
    response_model=IdeaQueryResponse,
    summary="Query ideas",
)
def query_ideas(
    request: IdeaQueryRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_ideas_data_source_id),
) -> IdeaQueryResponse:
    """Query ideas from the configured ideas data source.

    If name_filter is provided, results are fuzzy-matched and limited to top 5.
    """
    logger.debug("Querying ideas")
    try:
        filter_ = _build_idea_filter(request)
        # Default sort by last edited time descending (latest first)
        sorts = [{"timestamp": "last_edited_time", "direction": "descending"}]
        pages_data = client.query_all_data_source(data_source_id, filter_=filter_, sorts=sorts)

        # Parse all pages to idea responses
        items = [_idea_to_response(parse_page_to_idea(page)) for page in pages_data]

        # Apply fuzzy name filter if provided
        filtered_items, fuzzy_quality = filter_by_fuzzy_name(
            items=items,
            name_filter=request.name_filter,
            name_getter=lambda i: i.idea,
            limit=request.limit if not request.name_filter else 5,
        )

        return IdeaQueryResponse(
            results=filtered_items,
            fuzzy_match_quality=fuzzy_quality,
        )
    except NotionClientError as e:
        logger.exception(f"Failed to query ideas: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/{idea_id}",
    response_model=IdeaResponse,
    summary="Get idea",
)
def get_idea(
    idea_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> IdeaResponse:
    """Retrieve a single idea with its content."""
    logger.debug(f"Retrieving idea: {idea_id}")
    try:
        data = client.get_page(idea_id)
        idea = parse_page_to_idea(data)

        # Fetch page content
        blocks = client.get_page_content(idea_id)
        content = blocks_to_markdown(blocks) if blocks else None

        return _idea_to_response(idea, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve idea: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=IdeaBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ideas",
)
def create_ideas(
    requests: list[IdeaCreateRequest],
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_ideas_data_source_id),
) -> IdeaBulkCreateResponse:
    """Create one or more ideas in the ideas data source.

    Processes all items and returns both successes and failures.
    Partial success is possible - some items may be created while others fail.
    """
    logger.debug(f"Creating {len(requests)} ideas")
    created: list[IdeaResponse] = []
    failed: list[BulkCreateFailure] = []

    for request in requests:
        try:
            check_duplicate_name(
                client=client,
                data_source_id=data_source_id,
                name_property="Idea",
                complete_status=IdeaStatus.DONE.value,
                new_name=request.idea,
            )

            properties = build_idea_properties(
                idea=request.idea,
                status=request.status,
                idea_group=request.idea_group,
            )
            data = client.create_page(
                data_source_id=data_source_id,
                properties=properties,
            )
            idea = parse_page_to_idea(data)

            # Append content if provided
            if request.content:
                blocks = markdown_to_blocks(request.content)
                client.append_page_content(idea.id, blocks)

            created.append(_idea_to_response(idea, content=request.content))
        except (NotionClientError, HTTPException) as e:
            error_msg = e.detail if isinstance(e, HTTPException) else str(e)
            logger.warning(f"Failed to create idea '{request.idea}': {error_msg}")
            failed.append(BulkCreateFailure(name=request.idea, error=error_msg))

    return IdeaBulkCreateResponse(created=created, failed=failed)


@router.patch(
    "/{idea_id}",
    response_model=IdeaResponse,
    summary="Update idea",
)
def update_idea(
    idea_id: str,
    request: IdeaUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_ideas_data_source_id),
) -> IdeaResponse:
    """Update an idea's properties and/or content."""
    logger.debug(f"Updating idea: {idea_id}")

    if request.idea is not None:
        check_duplicate_name(
            client=client,
            data_source_id=data_source_id,
            name_property="Idea",
            complete_status=IdeaStatus.DONE.value,
            new_name=request.idea,
            exclude_id=idea_id,
        )

    try:
        properties = build_idea_properties(
            idea=request.idea,
            status=request.status,
            idea_group=request.idea_group,
        )

        if not properties and request.content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties or content to update.",
            )

        # Update properties if any
        if properties:
            data = client.update_page(page_id=idea_id, properties=properties)
            idea = parse_page_to_idea(data)
        else:
            # Content-only update - fetch current idea
            data = client.get_page(idea_id)
            idea = parse_page_to_idea(data)

        # Replace content if provided
        content: str | None
        if request.content is not None:
            new_blocks = markdown_to_blocks(request.content)
            client.replace_page_content(idea_id, new_blocks)
            content = request.content
        else:
            # Fetch existing content
            blocks = client.get_page_content(idea_id)
            content = blocks_to_markdown(blocks) if blocks else None

        return _idea_to_response(idea, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to update idea: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _build_idea_filter(request: IdeaQueryRequest) -> dict[str, object] | None:
    """Build Notion filter from structured query request.

    :param request: Query request with filter fields.
    :returns: Notion filter dictionary or None if no filters.
    """
    conditions: list[dict[str, object]] = []

    # Exclude Archived ideas by default unless include_done is True
    if not request.include_done:
        conditions.append(
            {"property": "Status", "status": {"does_not_equal": IdeaStatus.DONE.value}}
        )

    if request.status:
        conditions.append({"property": "Status", "status": {"equals": request.status.value}})

    if request.idea_group:
        conditions.append(
            {"property": "Idea Group", "select": {"equals": request.idea_group.value}}
        )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def _idea_to_response(idea: NotionIdea, content: str | None = None) -> IdeaResponse:
    """Convert a NotionIdea to an IdeaResponse.

    :param idea: The NotionIdea to convert.
    :param content: Optional markdown content for the page.
    :returns: IdeaResponse with all fields.
    """
    return IdeaResponse(
        id=idea.id,
        idea=idea.idea,
        status=idea.status,
        idea_group=idea.idea_group,
        content=content,
    )
