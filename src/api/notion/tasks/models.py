"""Pydantic models for Notion API endpoints."""

from datetime import date

from pydantic import BaseModel, Field

from src.api.notion.common.utils import FuzzyMatchQuality
from src.notion.enums import EffortLevel, Priority, TaskGroup, TaskStatus


class TaskResponse(BaseModel):
    """Response model for task endpoints with all fields."""

    id: str = Field(..., description="Task page ID")
    task_name: str = Field(..., description="Task title")
    status: str | None = Field(None, description="Task status")
    due_date: date | None = Field(None, description="Task due date")
    priority: str | None = Field(None, description="Task priority")
    effort_level: str | None = Field(None, description="Task effort level")
    task_group: str | None = Field(None, description="Work or Personal category")
    assignee: str | None = Field(None, description="Assigned user name")
    url: str = Field(..., description="Notion page URL")
    content: str | None = Field(None, description="Page content in markdown format")


class TaskCreateRequest(BaseModel):
    """Request model for task creation with validated enum fields."""

    task_name: str = Field(..., min_length=1, description="Task title")
    status: TaskStatus | None = Field(
        default=TaskStatus.NOT_STARTED,
        description=f"Task status (default: {TaskStatus.NOT_STARTED}) ({', '.join(TaskStatus)})",
    )
    due_date: date = Field(..., description="Task due date")
    priority: Priority | None = Field(
        default=Priority.LOW,
        description=f"Task priority (default: {Priority.LOW}) ({', '.join(Priority)})",
    )
    effort_level: EffortLevel | None = Field(
        default=EffortLevel.SMALL,
        description=f"Task effort level (default: {EffortLevel.SMALL}) ({', '.join(EffortLevel)})",
    )
    task_group: TaskGroup = Field(..., description=f"Task group category ({', '.join(TaskGroup)})")
    content: str | None = Field(None, description="Markdown content for the task page body")


class TaskUpdateRequest(BaseModel):
    """Request model for task update with validated enum fields."""

    task_name: str | None = Field(None, min_length=1, description="Task title")
    status: TaskStatus | None = Field(None, description=f"Task status ({', '.join(TaskStatus)})")
    due_date: date | None = Field(None, description="Task due date")
    priority: Priority | None = Field(None, description=f"Task priority ({', '.join(Priority)})")
    effort_level: EffortLevel | None = Field(
        None, description=f"Task effort level ({', '.join(EffortLevel)})"
    )
    task_group: TaskGroup | None = Field(
        None, description=f"Task group category ({', '.join(TaskGroup)})"
    )
    content: str | None = Field(
        None, description="Markdown content to replace page body (if provided)"
    )


class TaskQueryRequest(BaseModel):
    """Request model for task query endpoint with structured filters."""

    name_filter: str | None = Field(
        None, description="Fuzzy match against task name (returns top 5 matches)"
    )
    include_done: bool = Field(
        False, description="Whether to include completed tasks (default: exclude)"
    )
    status: TaskStatus | None = Field(
        None, description=f"Filter by task status ({', '.join(TaskStatus)})"
    )
    priority: Priority | None = Field(
        None, description=f"Filter by priority ({', '.join(Priority)})"
    )
    effort_level: EffortLevel | None = Field(
        None, description=f"Filter by effort level ({', '.join(EffortLevel)})"
    )
    task_group: TaskGroup | None = Field(
        None, description=f"Filter by task group ({', '.join(TaskGroup)})"
    )
    limit: int = Field(50, ge=1, le=100, description="Maximum number of tasks to return")


class TaskQueryResponse(BaseModel):
    """Response model for task query endpoint."""

    results: list[TaskResponse] = Field(
        default_factory=list,
        description="List of tasks matching the query",
    )
    fuzzy_match_quality: FuzzyMatchQuality | None = Field(
        None,
        description=(
            "Quality of fuzzy name match: None=unfiltered, "
            "'good'=best match score >= 60, 'weak'=no matches above threshold"
        ),
    )
    excluded_done: bool = Field(
        False,
        description="True if completed tasks were excluded from results",
    )
