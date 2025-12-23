"""Pydantic models for Notion API endpoints."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

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
    description: str | None = Field(None, description="Task description")
    assignee: str | None = Field(None, description="Assigned user name")
    url: str = Field(..., description="Notion page URL")


class TaskCreateRequest(BaseModel):
    """Request model for task creation with validated enum fields."""

    task_name: str = Field(..., min_length=1, description="Task title")
    status: TaskStatus | None = Field(None, description="Task status")
    due_date: date | None = Field(None, description="Task due date")
    priority: Priority | None = Field(None, description="Task priority")
    effort_level: EffortLevel | None = Field(None, description="Task effort level")
    task_group: TaskGroup | None = Field(None, description="Task group category")
    description: str | None = Field(None, description="Task description")


class TaskUpdateRequest(BaseModel):
    """Request model for task update with validated enum fields."""

    task_name: str | None = Field(None, min_length=1, description="Task title")
    status: TaskStatus | None = Field(None, description="Task status")
    due_date: date | None = Field(None, description="Task due date")
    priority: Priority | None = Field(None, description="Task priority")
    effort_level: EffortLevel | None = Field(None, description="Task effort level")
    task_group: TaskGroup | None = Field(None, description="Task group category")
    description: str | None = Field(None, description="Task description")


class TaskQueryRequest(BaseModel):
    """Request model for task query endpoint."""

    filter: dict[str, Any] | None = Field(
        None,
        description="Notion filter object",
    )
    sorts: list[dict[str, Any]] | None = Field(
        None,
        description="List of sort objects",
    )


class TaskQueryResponse(BaseModel):
    """Response model for task query endpoint."""

    results: list[TaskResponse] = Field(
        default_factory=list,
        description="List of all tasks matching the query",
    )
