"""Notion API endpoints for managing databases, data sources, pages, and tasks."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.notion.dependencies import get_data_source_id, get_notion_client
from src.api.notion.tasks.models import (
    TaskCreateRequest,
    TaskQueryRequest,
    TaskQueryResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from src.notion.client import NotionClient
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
    data_source_id: str = Depends(get_data_source_id),
) -> TaskQueryResponse:
    """Query all tasks from the configured task tracker."""
    logger.debug("Querying tasks")
    try:
        pages_data = client.query_all_data_source(
            data_source_id,
            filter_=request.filter,
            sorts=request.sorts,
        )
        tasks = [_task_to_response(parse_page_to_task(page)) for page in pages_data]
        return TaskQueryResponse(results=tasks)
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
        return _task_to_response(task)
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
    data_source_id: str = Depends(get_data_source_id),
) -> TaskResponse:
    """Create a new task in the task tracker."""
    logger.debug("Creating task")
    try:
        properties = build_task_properties(
            task_name=request.task_name,
            status=request.status,
            due_date=request.due_date,
            priority=request.priority,
            effort_level=request.effort_level,
            task_group=request.task_group,
            description=request.description,
        )
        data = client.create_page(
            data_source_id=data_source_id,
            properties=properties,
        )
        task = parse_page_to_task(data)
        return _task_to_response(task)
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
) -> TaskResponse:
    """Update a task's properties."""
    logger.debug(f"Updating task: {task_id}")
    try:
        properties = build_task_properties(
            task_name=request.task_name,
            status=request.status,
            due_date=request.due_date,
            priority=request.priority,
            effort_level=request.effort_level,
            task_group=request.task_group,
            description=request.description,
        )

        if not properties:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No properties to update.",
            )

        data = client.update_page(page_id=task_id, properties=properties)
        task = parse_page_to_task(data)
        return _task_to_response(task)
    except NotionClientError as e:
        logger.exception(f"Failed to update task: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


def _task_to_response(task: NotionTask) -> TaskResponse:
    """Convert a NotionTask to a TaskResponse."""
    return TaskResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        due_date=task.due_date,
        priority=task.priority,
        effort_level=task.effort_level,
        task_group=task.task_group,
        assignee=task.assignee,
        url=task.url,
    )
