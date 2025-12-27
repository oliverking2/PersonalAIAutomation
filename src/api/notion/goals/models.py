"""Pydantic models for Goals API endpoints."""

from datetime import date

from pydantic import BaseModel, Field

from src.api.notion.common.utils import FuzzyMatchQuality
from src.notion.enums import GoalCategory, GoalStatus, Priority


class GoalResponse(BaseModel):
    """Response model for goal endpoints."""

    id: str = Field(..., description="Goal page ID")
    goal_name: str = Field(..., description="Goal title")
    status: str | None = Field(None, description="Goal status")
    priority: str | None = Field(None, description="Goal priority")
    category: str | None = Field(None, description="Goal category")
    progress: float | None = Field(None, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")
    content: str | None = Field(None, description="Page content in markdown format")


class GoalCreateRequest(BaseModel):
    """Request model for goal creation with validated enum fields."""

    goal_name: str = Field(..., min_length=1, description="Goal title")
    status: GoalStatus | None = Field(
        default=GoalStatus.NOT_STARTED,
        description=f"Goal status (default: {GoalStatus.NOT_STARTED}) ({', '.join(GoalStatus)})",
    )
    priority: Priority | None = Field(None, description=f"Goal priority ({', '.join(Priority)})")
    category: GoalCategory | None = Field(
        None, description=f"Goal category ({', '.join(GoalCategory)})"
    )
    progress: float | None = Field(None, ge=0, le=100, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")
    content: str | None = Field(None, description="Markdown content for the goal page body")


class GoalUpdateRequest(BaseModel):
    """Request model for goal update with validated enum fields."""

    goal_name: str | None = Field(None, min_length=1, description="Goal title")
    status: GoalStatus | None = Field(None, description=f"Goal status ({', '.join(GoalStatus)})")
    priority: Priority | None = Field(None, description=f"Goal priority ({', '.join(Priority)})")
    category: GoalCategory | None = Field(
        None, description=f"Goal category ({', '.join(GoalCategory)})"
    )
    progress: float | None = Field(None, ge=0, le=100, description="Goal progress (0-100)")
    due_date: date | None = Field(None, description="Goal due date")
    content: str | None = Field(
        None, description="Markdown content to replace page body (if provided)"
    )


class GoalQueryRequest(BaseModel):
    """Request model for goal query endpoint with structured filters."""

    name_filter: str | None = Field(
        None, description="Fuzzy match against goal name (returns top 5 matches)"
    )
    include_done: bool = Field(
        False, description="Whether to include completed goals (default: exclude)"
    )
    status: GoalStatus | None = Field(
        None, description=f"Filter by goal status ({', '.join(GoalStatus)})"
    )
    priority: Priority | None = Field(
        None, description=f"Filter by priority ({', '.join(Priority)})"
    )
    category: GoalCategory | None = Field(
        None, description=f"Filter by category ({', '.join(GoalCategory)})"
    )
    due_before: date | None = Field(
        None, description="Filter goals due before this date (exclusive)"
    )
    due_after: date | None = Field(None, description="Filter goals due after this date (exclusive)")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of goals to return")


class GoalQueryResponse(BaseModel):
    """Response model for goal query endpoint."""

    results: list[GoalResponse] = Field(
        default_factory=list,
        description="List of goals matching the query",
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
        description="True if completed goals were excluded from results",
    )
