"""Notion API endpoints for managing projects."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.models import BulkCreateFailure
from src.api.notion.common.utils import check_duplicate_name, filter_by_fuzzy_name
from src.api.notion.dependencies import get_notion_client, get_projects_data_source_id
from src.api.notion.projects.models import (
    ProjectBulkCreateResponse,
    ProjectCreateRequest,
    ProjectQueryRequest,
    ProjectQueryResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from src.notion.blocks import (
    UnsupportedBlockTypeError,
    blocks_to_markdown,
    markdown_to_blocks,
)
from src.notion.client import NotionClient
from src.notion.enums import ProjectStatus
from src.notion.exceptions import NotionClientError
from src.notion.models import NotionProject
from src.notion.parser import build_project_properties, parse_page_to_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Notion - Projects"])


@router.post(
    "/query",
    response_model=ProjectQueryResponse,
    summary="Query projects",
)
def query_projects(
    request: ProjectQueryRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_projects_data_source_id),
) -> ProjectQueryResponse:
    """Query projects from the configured projects tracker.

    By default, completed projects are excluded unless include_done=True.
    If name_filter is provided, results are fuzzy-matched and limited to top 5.
    """
    start = time.perf_counter()
    logger.info(
        f"Query projects: name_filter={request.name_filter!r}, status={request.status}, "
        f"priority={request.priority}, include_done={request.include_done}"
    )
    try:
        filter_ = _build_project_filter(request)
        # Default sort by last edited time descending (latest first)
        sorts = [{"timestamp": "last_edited_time", "direction": "descending"}]
        pages_data = client.query_all_data_source(data_source_id, filter_=filter_, sorts=sorts)

        # Parse all pages to project responses
        projects = [_project_to_response(parse_page_to_project(page)) for page in pages_data]

        # Apply fuzzy name filter if provided
        filtered_projects, fuzzy_quality = filter_by_fuzzy_name(
            items=projects,
            name_filter=request.name_filter,
            name_getter=lambda p: p.project_name,
            limit=request.limit if not request.name_filter else 5,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Query projects complete: found={len(pages_data)}, "
            f"returned={len(filtered_projects)}, elapsed={elapsed_ms:.0f}ms"
        )

        return ProjectQueryResponse(
            results=filtered_projects,
            fuzzy_match_quality=fuzzy_quality,
            excluded_done=not request.include_done,
        )
    except NotionClientError as e:
        logger.exception(
            f"Failed to query projects: name_filter={request.name_filter!r}, "
            f"status={request.status}, error={e}"
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project",
)
def get_project(
    project_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> ProjectResponse:
    """Retrieve a single project."""
    start = time.perf_counter()
    logger.info(f"Get project: id={project_id}")
    try:
        data = client.get_page(project_id)
        project = parse_page_to_project(data)

        # Fetch page content
        blocks = client.get_page_content(project_id)
        content = blocks_to_markdown(blocks) if blocks else None

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Get project complete: id={project_id}, name={project.project_name!r}, "
            f"has_content={content is not None}, elapsed={elapsed_ms:.0f}ms"
        )

        return _project_to_response(project, content=content)
    except UnsupportedBlockTypeError as e:
        logger.warning(f"Get project failed - unsupported blocks: id={project_id}, error={e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except NotionClientError as e:
        logger.exception(f"Failed to get project: id={project_id}, error={e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=ProjectBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create projects",
)
def create_projects(
    requests: list[ProjectCreateRequest],
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_projects_data_source_id),
) -> ProjectBulkCreateResponse:
    """Create one or more projects in the projects tracker.

    Processes all items and returns both successes and failures.
    Partial success is possible - some items may be created while others fail.
    """
    start = time.perf_counter()
    logger.info(f"Create projects: count={len(requests)}")
    created: list[ProjectResponse] = []
    failed: list[BulkCreateFailure] = []

    for i, request in enumerate(requests):
        try:
            check_duplicate_name(
                client=client,
                data_source_id=data_source_id,
                name_property="Project name",
                complete_status="Completed",
                new_name=request.project_name,
            )

            properties = build_project_properties(
                project_name=request.project_name,
                status=request.status,
                priority=request.priority,
                project_group=request.project_group,
            )
            data = client.create_page(
                data_source_id=data_source_id,
                properties=properties,
            )
            project = parse_page_to_project(data)

            # Append content if provided
            if request.content:
                blocks = markdown_to_blocks(request.content)
                client.append_page_content(project.id, blocks)

            created.append(_project_to_response(project, content=request.content))
            logger.debug(f"Create projects [{i + 1}/{len(requests)}]: created id={project.id}")
        except (NotionClientError, HTTPException) as e:
            error_msg = e.detail if isinstance(e, HTTPException) else str(e)
            logger.warning(
                f"Create projects [{i + 1}/{len(requests)}]: "
                f"failed name={request.project_name!r}, error={error_msg}"
            )
            failed.append(BulkCreateFailure(name=request.project_name, error=error_msg))

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Create projects complete: succeeded={len(created)}, "
        f"failed={len(failed)}, elapsed={elapsed_ms:.0f}ms"
    )

    return ProjectBulkCreateResponse(created=created, failed=failed)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
)
def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_projects_data_source_id),
) -> ProjectResponse:
    """Update a project's properties."""
    start = time.perf_counter()
    fields = list(request.model_dump(exclude_unset=True).keys())
    logger.info(f"Update project: id={project_id}, fields={fields}")

    if request.project_name is not None:
        check_duplicate_name(
            client=client,
            data_source_id=data_source_id,
            name_property="Project name",
            complete_status="Completed",
            new_name=request.project_name,
            exclude_id=project_id,
        )

    try:
        properties = build_project_properties(
            project_name=request.project_name,
            status=request.status,
            priority=request.priority,
            project_group=request.project_group,
        )

        if not properties and request.content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties or content to update.",
            )

        # Check for unsupported blocks before replacing content
        if request.content is not None:
            existing_blocks = client.get_page_content(project_id)
            if existing_blocks:
                blocks_to_markdown(existing_blocks)  # Raises if unsupported

        # Update properties if any
        if properties:
            data = client.update_page(page_id=project_id, properties=properties)
            project = parse_page_to_project(data)
        else:
            # Content-only update - fetch current project
            data = client.get_page(project_id)
            project = parse_page_to_project(data)

        # Replace content if provided
        content: str | None
        if request.content is not None:
            new_blocks = markdown_to_blocks(request.content)
            client.replace_page_content(project_id, new_blocks)
            content = request.content
        else:
            # Fetch existing content
            blocks = client.get_page_content(project_id)
            content = blocks_to_markdown(blocks) if blocks else None

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Update project complete: id={project_id}, name={project.project_name!r}, "
            f"elapsed={elapsed_ms:.0f}ms"
        )

        return _project_to_response(project, content=content)
    except UnsupportedBlockTypeError as e:
        logger.warning(f"Update project failed - unsupported blocks: id={project_id}, error={e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except NotionClientError as e:
        logger.exception(f"Failed to update project: id={project_id}, fields={fields}, error={e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _build_project_filter(request: ProjectQueryRequest) -> dict[str, object] | None:
    """Build Notion filter from structured query request.

    :param request: Query request with filter fields.
    :returns: Notion filter dictionary or None if no filters.
    """
    conditions: list[dict[str, object]] = []

    # Exclude Completed projects by default unless include_done is True
    if not request.include_done:
        conditions.append(
            {"property": "Status", "status": {"does_not_equal": ProjectStatus.COMPLETED.value}}
        )

    if request.status:
        conditions.append({"property": "Status", "status": {"equals": request.status.value}})

    if request.priority:
        conditions.append({"property": "Priority", "select": {"equals": request.priority.value}})

    if request.project_group:
        conditions.append(
            {"property": "Project Group", "select": {"equals": request.project_group.value}}
        )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def _project_to_response(project: NotionProject, content: str | None = None) -> ProjectResponse:
    """Convert a NotionProject to a ProjectResponse.

    :param project: The NotionProject to convert.
    :param content: Optional markdown content for the page.
    :returns: ProjectResponse with all fields.
    """
    return ProjectResponse(
        id=project.id,
        project_name=project.project_name,
        status=project.status,
        priority=project.priority,
        project_group=project.project_group,
        content=content,
    )
