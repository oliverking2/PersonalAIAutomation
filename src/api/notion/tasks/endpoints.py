"""Notion API endpoints for managing databases, data sources, pages, and tasks."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.common.utils import check_duplicate_name, filter_by_fuzzy_name
from src.api.notion.dependencies import get_notion_client, get_task_data_source_id
from src.api.notion.tasks.models import (
    TaskCreateRequest,
    TaskQueryRequest,
    TaskQueryResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from src.notion.blocks import blocks_to_markdown, markdown_to_blocks
from src.notion.client import NotionClient
from src.notion.enums import TaskStatus
from src.notion.exceptions import NotionClientError
from src.notion.models import NotionTask
from src.notion.parser import build_task_properties, parse_page_to_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Notion - Task Management"])


@router.post(
    "/query",
    response_model=TaskQueryResponse,
    summary="Query tasks",
)
def query_tasks(
    request: TaskQueryRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_task_data_source_id),
) -> TaskQueryResponse:
    """Query tasks from the configured task tracker.

    By default, completed (Done) tasks are excluded unless include_done=True.
    If name_filter is provided, results are fuzzy-matched and limited to top 5.
    """
    logger.debug("Querying tasks")
    try:
        filter_ = _build_task_filter(request)
        # Default sort by last edited time descending (latest first)
        sorts = [{"timestamp": "last_edited_time", "direction": "descending"}]
        pages_data = client.query_all_data_source(data_source_id, filter_=filter_, sorts=sorts)

        # Parse all pages to task responses
        tasks = [_task_to_response(parse_page_to_task(page)) for page in pages_data]

        # Apply fuzzy name filter if provided
        filtered_tasks, fuzzy_quality = filter_by_fuzzy_name(
            items=tasks,
            name_filter=request.name_filter,
            name_getter=lambda t: t.task_name,
            limit=request.limit if not request.name_filter else 5,
        )

        return TaskQueryResponse(
            results=filtered_tasks,
            fuzzy_match_quality=fuzzy_quality,
            excluded_done=not request.include_done,
        )
    except NotionClientError as e:
        logger.exception(f"Failed to query tasks: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task",
)
def get_task(
    task_id: str,
    client: NotionClient = Depends(get_notion_client),
) -> TaskResponse:
    """Retrieve a single task."""
    logger.debug(f"Retrieving task: {task_id}")
    try:
        data = client.get_page(task_id)
        task = parse_page_to_task(data)

        # Fetch page content
        blocks = client.get_page_content(task_id)
        content = blocks_to_markdown(blocks) if blocks else None

        return _task_to_response(task, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to retrieve task: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task",
)
def create_task(
    request: TaskCreateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_task_data_source_id),
) -> TaskResponse:
    """Create a new task in the task tracker."""
    logger.debug("Creating task")

    check_duplicate_name(
        client=client,
        data_source_id=data_source_id,
        name_property="Task name",
        complete_status="Done",
        new_name=request.task_name,
    )

    try:
        properties = build_task_properties(
            task_name=request.task_name,
            status=request.status,
            due_date=request.due_date,
            priority=request.priority,
            effort_level=request.effort_level,
            task_group=request.task_group,
        )
        data = client.create_page(
            data_source_id=data_source_id,
            properties=properties,
        )
        task = parse_page_to_task(data)

        # Append content if provided
        if request.content:
            blocks = markdown_to_blocks(request.content)
            client.append_page_content(task.id, blocks)

        return _task_to_response(task, content=request.content)
    except NotionClientError as e:
        logger.exception(f"Failed to create task: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update task",
)
def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    client: NotionClient = Depends(get_notion_client),
    data_source_id: str = Depends(get_task_data_source_id),
) -> TaskResponse:
    """Update a task's properties."""
    logger.debug(f"Updating task: {task_id}")

    if request.task_name is not None:
        check_duplicate_name(
            client=client,
            data_source_id=data_source_id,
            name_property="Task name",
            complete_status="Done",
            new_name=request.task_name,
            exclude_id=task_id,
        )

    try:
        properties = build_task_properties(
            task_name=request.task_name,
            status=request.status,
            due_date=request.due_date,
            priority=request.priority,
            effort_level=request.effort_level,
            task_group=request.task_group,
        )

        if not properties and request.content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties or content to update.",
            )

        # Update properties if any
        if properties:
            data = client.update_page(page_id=task_id, properties=properties)
            task = parse_page_to_task(data)
        else:
            # Content-only update - fetch current task
            data = client.get_page(task_id)
            task = parse_page_to_task(data)

        # Replace content if provided
        content: str | None
        if request.content is not None:
            new_blocks = markdown_to_blocks(request.content)
            client.replace_page_content(task_id, new_blocks)
            content = request.content
        else:
            # Fetch existing content
            blocks = client.get_page_content(task_id)
            content = blocks_to_markdown(blocks) if blocks else None

        return _task_to_response(task, content=content)
    except NotionClientError as e:
        logger.exception(f"Failed to update task: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _build_task_filter(request: TaskQueryRequest) -> dict[str, object] | None:
    """Build Notion filter from structured query request.

    :param request: Query request with filter fields.
    :returns: Notion filter dictionary or None if no filters.
    """
    conditions: list[dict[str, object]] = []

    # Exclude Done tasks by default unless include_done is True
    if not request.include_done:
        conditions.append(
            {"property": "Status", "status": {"does_not_equal": TaskStatus.DONE.value}}
        )

    if request.status:
        conditions.append({"property": "Status", "status": {"equals": request.status.value}})

    if request.priority:
        conditions.append({"property": "Priority", "select": {"equals": request.priority.value}})

    if request.effort_level:
        conditions.append(
            {"property": "Effort level", "select": {"equals": request.effort_level.value}}
        )

    if request.task_group:
        conditions.append(
            {"property": "Task Group", "select": {"equals": request.task_group.value}}
        )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


def _task_to_response(task: NotionTask, content: str | None = None) -> TaskResponse:
    """Convert a NotionTask to a TaskResponse.

    :param task: The NotionTask to convert.
    :param content: Optional markdown content for the page.
    :returns: TaskResponse with all fields.
    """
    return TaskResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        due_date=task.due_date,
        priority=task.priority,
        effort_level=task.effort_level,
        task_group=task.task_group,
        assignee=task.assignee,
        notion_url=task.notion_url,
        content=content,
    )
