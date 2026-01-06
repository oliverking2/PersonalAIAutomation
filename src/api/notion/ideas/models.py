"""Pydantic models for Ideas API endpoints."""

from pydantic import BaseModel, Field

from src.api.notion.common.models import BulkCreateFailure
from src.api.notion.common.utils import FuzzyMatchQuality
from src.notion.enums import IdeaGroup, IdeaStatus


class IdeaResponse(BaseModel):
    """Response model for idea endpoints."""

    id: str = Field(..., description="Idea page ID")
    idea: str = Field(..., description="Idea title")
    status: str | None = Field(None, description="Idea status")
    idea_group: str | None = Field(None, description="Idea group (Work/Personal)")
    content: str | None = Field(None, description="Page content in markdown format")


class IdeaCreateRequest(BaseModel):
    """Request model for idea creation with validated enum fields."""

    idea: str = Field(..., min_length=1, description="Idea title")
    status: IdeaStatus | None = Field(
        default=IdeaStatus.NOT_STARTED,
        description=f"Idea status (default: {IdeaStatus.NOT_STARTED}) ({', '.join(IdeaStatus)})",
    )
    idea_group: IdeaGroup = Field(..., description=f"Idea group ({', '.join(IdeaGroup)})")
    content: str | None = Field(None, description="Markdown content for the idea page body")


class IdeaUpdateRequest(BaseModel):
    """Request model for idea update with validated enum fields."""

    idea: str | None = Field(None, min_length=1, description="Idea title")
    status: IdeaStatus | None = Field(None, description=f"Idea status ({', '.join(IdeaStatus)})")
    idea_group: IdeaGroup | None = Field(None, description=f"Idea group ({', '.join(IdeaGroup)})")
    content: str | None = Field(
        None, description="Markdown content to replace page body (if provided)"
    )


class IdeaQueryRequest(BaseModel):
    """Request model for idea query endpoint with structured filters."""

    name_filter: str | None = Field(
        None, description="Fuzzy match against idea title (returns top 5 matches)"
    )
    include_done: bool = Field(
        False, description="Whether to include done ideas (default: exclude)"
    )
    status: IdeaStatus | None = Field(
        None, description=f"Filter by idea status ({', '.join(IdeaStatus)})"
    )
    idea_group: IdeaGroup | None = Field(
        None, description=f"Filter by idea group ({', '.join(IdeaGroup)})"
    )
    limit: int = Field(50, ge=1, le=100, description="Maximum number of items to return")


class IdeaQueryResponse(BaseModel):
    """Response model for idea query endpoint."""

    results: list[IdeaResponse] = Field(
        default_factory=list,
        description="List of ideas matching the query",
    )
    fuzzy_match_quality: FuzzyMatchQuality | None = Field(
        None,
        description=(
            "Quality of fuzzy name match: None=unfiltered, "
            "'good'=best match score >= 60, 'weak'=no matches above threshold"
        ),
    )


class IdeaBulkCreateResponse(BaseModel):
    """Response model for bulk idea creation with partial success support."""

    created: list[IdeaResponse] = Field(
        default_factory=list,
        description="Successfully created ideas",
    )
    failed: list[BulkCreateFailure] = Field(
        default_factory=list,
        description="Ideas that failed to create with error details",
    )
