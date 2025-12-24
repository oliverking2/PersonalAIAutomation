"""Pydantic models for Goals API endpoints."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from src.notion.enums import GoalStatus, Priority


class GoalResponse(BaseModel):
    """Response model for goal endpoints."""

    id: str = Field(..., description="Goal page ID")
    goal_name: str = Field(..., description="Goal title")
    status: str | None = Field(None, description="Goal status")
    priority: str | None = Field(None, description="Goal priority")
    progress: float | None = Field(None, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")
    url: str = Field(..., description="Notion page URL")


class GoalCreateRequest(BaseModel):
    """Request model for goal creation with validated enum fields."""

    goal_name: str = Field(..., min_length=1, description="Goal title")
    status: GoalStatus | None = Field(default=GoalStatus.NOT_STARTED, description="Goal status")
    priority: Priority | None = Field(None, description="Goal priority")
    progress: float | None = Field(None, ge=0, le=100, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")


class GoalUpdateRequest(BaseModel):
    """Request model for goal update with validated enum fields."""

    goal_name: str | None = Field(None, min_length=1, description="Goal title")
    status: GoalStatus | None = Field(None, description="Goal status")
    priority: Priority | None = Field(None, description="Goal priority")
    progress: float | None = Field(None, ge=0, le=100, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")


class GoalQueryRequest(BaseModel):
    """Request model for goal query endpoint."""

    filter: dict[str, Any] | None = Field(
        None,
        description="Notion filter object",
    )
    sorts: list[dict[str, Any]] | None = Field(
        None,
        description="List of sort objects",
    )


class GoalQueryResponse(BaseModel):
    """Response model for goal query endpoint."""

    results: list[GoalResponse] = Field(
        default_factory=list,
        description="List of all goals matching the query",
    )
