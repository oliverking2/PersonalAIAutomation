"""Tasks tool handlers for the AI agent.

These tools are thin wrappers around the API endpoints. All business logic,
validation, and Notion interaction is handled by the API layer.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.agent.api_client import AgentAPIClient
from src.agent.enums import RiskLevel
from src.agent.models import ToolDef
from src.api.notion.tasks.models import (
    TaskCreateRequest,
    TaskQueryRequest,
    TaskUpdateRequest,
)
from src.notion.enums import EffortLevel, Priority, TaskGroup, TaskStatus

logger = logging.getLogger(__name__)


def _get_client() -> AgentAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return AgentAPIClient()


# --- Argument Models ---
# Only define models for tool-specific arguments not covered by API models.


class GetTaskArgs(BaseModel):
    """Arguments for getting a task by ID."""

    task_id: str = Field(..., min_length=1, description="The Notion page ID of the task")


class UpdateTaskArgs(TaskUpdateRequest):
    """Arguments for updating a task (extends API model with task_id)."""

    task_id: str = Field(..., min_length=1, description="The Notion page ID to update")


# --- Tool Handlers ---


def query_tasks(args: TaskQueryRequest) -> dict[str, Any]:
    """Query tasks via API.

    :param args: Query arguments with optional filters.
    :returns: Dictionary with 'items' list and 'count'.
    """
    logger.debug(f"Querying tasks: status={args.status}, priority={args.priority}")

    with _get_client() as client:
        response = client.post(
            "/notion/tasks/query",
            json=args.model_dump(mode="json", exclude_none=True),
        )

    items = response.get("results", [])
    return {"items": items, "count": len(items)}


def get_task(args: GetTaskArgs) -> dict[str, Any]:
    """Get a single task by ID via API.

    :param args: Arguments containing the task ID.
    :returns: Dictionary with the task details.
    """
    logger.debug(f"Getting task: {args.task_id}")

    with _get_client() as client:
        response = client.get(f"/notion/tasks/{args.task_id}")

    return {"item": response}


def create_task(args: TaskCreateRequest) -> dict[str, Any]:
    """Create a new task via API.

    :param args: Arguments for the new task.
    :returns: Dictionary with the created task details.
    """
    logger.debug(f"Creating task: {args.task_name}")

    with _get_client() as client:
        response = client.post(
            "/notion/tasks",
            json=args.model_dump(mode="json", exclude_none=True),
        )

    return {"item": response, "created": True}


def update_task(args: UpdateTaskArgs) -> dict[str, Any]:
    """Update an existing task via API.

    :param args: Arguments for the update.
    :returns: Dictionary with the updated task details.
    """
    logger.debug(f"Updating task: {args.task_id}")

    # Exclude task_id from the payload (it's in the URL)
    payload = args.model_dump(mode="json", exclude_none=True, exclude={"task_id"})

    if not payload:
        return {"error": "No properties to update", "updated": False}

    with _get_client() as client:
        response = client.patch(f"/notion/tasks/{args.task_id}", json=payload)

    return {"item": response, "updated": True}


# --- Tool Definitions ---


def get_tasks_tools() -> list[ToolDef]:
    """Get all tasks tool definitions.

    :returns: List of ToolDef instances for tasks operations.
    """
    # Build dynamic descriptions from enums
    status_options = ", ".join(TaskStatus)
    priority_options = ", ".join(Priority)
    effort_options = ", ".join(EffortLevel)
    group_options = ", ".join(TaskGroup)

    return [
        ToolDef(
            name="query_tasks",
            description=(
                f"Query tasks from the task tracker. Can filter by status "
                f"({status_options}), priority ({priority_options}), "
                f"effort level ({effort_options}), and task group ({group_options})."
            ),
            tags=frozenset({"tasks", "query", "list"}),
            risk_level=RiskLevel.SAFE,
            args_model=TaskQueryRequest,
            handler=query_tasks,
        ),
        ToolDef(
            name="get_task",
            description=(
                "Get details of a specific task by its ID. "
                "Returns task name, status, due date, priority, effort level, and task group."
            ),
            tags=frozenset({"tasks", "get", "item"}),
            risk_level=RiskLevel.SAFE,
            args_model=GetTaskArgs,
            handler=get_task,
        ),
        ToolDef(
            name="create_task",
            description=(
                f"Create a new task. Requires a task name and a task group, task group ({group_options}) and due date. "
                f"Optional: status ({status_options}), priority ({priority_options}) and "
                f"effort level ({effort_options})."
            ),
            tags=frozenset({"tasks", "create", "item"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=TaskCreateRequest,
            handler=create_task,
        ),
        ToolDef(
            name="update_task",
            description=(
                f"Update an existing task. Requires the task ID. "
                f"Can update task name, status ({status_options}), "
                f"priority ({priority_options}), effort level ({effort_options}), "
                f"task group ({group_options}), or due date."
            ),
            tags=frozenset({"tasks", "update", "item"}),
            risk_level=RiskLevel.SENSITIVE,
            args_model=UpdateTaskArgs,
            handler=update_task,
        ),
    ]
