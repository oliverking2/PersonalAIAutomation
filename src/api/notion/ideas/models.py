"""Pydantic models for Ideas API endpoints."""

from pydantic import BaseModel, Field

from src.api.notion.common.utils import FuzzyMatchQuality
from src.notion.enums import IdeaGroup


class IdeaResponse(BaseModel):
    """Response model for idea endpoints."""

    id: str = Field(..., description="Idea page ID")
    idea: str = Field(..., description="Idea title")
    idea_group: str | None = Field(None, description="Idea group (Work/Personal)")
    notion_url: str = Field(..., description="Notion page URL")
    content: str | None = Field(None, description="Page content in markdown format")


class IdeaCreateRequest(BaseModel):
    """Request model for idea creation with validated enum fields."""

    idea: str = Field(..., min_length=1, description="Idea title")
    idea_group: IdeaGroup | None = Field(None, description=f"Idea group ({', '.join(IdeaGroup)})")
    content: str | None = Field(None, description="Markdown content for the idea page body")


class IdeaUpdateRequest(BaseModel):
    """Request model for idea update with validated enum fields."""

    idea: str | None = Field(None, min_length=1, description="Idea title")
    idea_group: IdeaGroup | None = Field(None, description=f"Idea group ({', '.join(IdeaGroup)})")
    content: str | None = Field(
        None, description="Markdown content to replace page body (if provided)"
    )


class IdeaQueryRequest(BaseModel):
    """Request model for idea query endpoint with structured filters."""

    name_filter: str | None = Field(
        None, description="Fuzzy match against idea title (returns top 5 matches)"
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
