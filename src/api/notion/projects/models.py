"""Pydantic models for Projects API endpoints."""

from pydantic import BaseModel, Field

from src.api.notion.common.models import BulkCreateFailure
from src.api.notion.common.utils import FuzzyMatchQuality
from src.notion.enums import ProjectGroup, ProjectPriority, ProjectStatus


class ProjectResponse(BaseModel):
    """Response model for project endpoints."""

    id: str = Field(..., description="Project page ID")
    project_name: str = Field(..., description="Project title")
    status: str | None = Field(None, description="Project status")
    priority: str | None = Field(None, description="Project priority")
    project_group: str | None = Field(None, description="Work or Personal category")
    content: str | None = Field(None, description="Page content in markdown format")


class ProjectCreateRequest(BaseModel):
    """Request model for project creation with validated enum fields."""

    project_name: str = Field(..., min_length=1, description="Project title")
    status: ProjectStatus | None = Field(
        default=ProjectStatus.NOT_STARTED,
        description=f"Project status (default: {ProjectStatus.NOT_STARTED}) ({', '.join(ProjectStatus)})",
    )
    priority: ProjectPriority | None = Field(
        None, description=f"Project priority ({', '.join(ProjectPriority)})"
    )
    project_group: ProjectGroup = Field(
        ..., description=f"Work or Personal category ({', '.join(ProjectGroup)})"
    )
    content: str | None = Field(None, description="Markdown content for the project page body")


class ProjectUpdateRequest(BaseModel):
    """Request model for project update with validated enum fields."""

    project_name: str | None = Field(None, min_length=1, description="Project title")
    status: ProjectStatus | None = Field(
        None, description=f"Project status ({', '.join(ProjectStatus)})"
    )
    priority: ProjectPriority | None = Field(
        None, description=f"Project priority ({', '.join(ProjectPriority)})"
    )
    project_group: ProjectGroup | None = Field(
        None, description=f"Work or Personal category ({', '.join(ProjectGroup)})"
    )
    content: str | None = Field(
        None, description="Markdown content to replace page body (if provided)"
    )


class ProjectQueryRequest(BaseModel):
    """Request model for project query endpoint with structured filters."""

    name_filter: str | None = Field(
        None, description="Fuzzy match against project name (returns top 5 matches)"
    )
    include_done: bool = Field(
        False, description="Whether to include completed projects (default: exclude)"
    )
    status: ProjectStatus | None = Field(
        None, description=f"Filter by project status ({', '.join(ProjectStatus)})"
    )
    priority: ProjectPriority | None = Field(
        None, description=f"Filter by priority ({', '.join(ProjectPriority)})"
    )
    project_group: ProjectGroup | None = Field(
        None, description=f"Filter by group ({', '.join(ProjectGroup)})"
    )
    limit: int = Field(50, ge=1, le=100, description="Maximum number of projects to return")


class ProjectQueryResponse(BaseModel):
    """Response model for project query endpoint."""

    results: list[ProjectResponse] = Field(
        default_factory=list,
        description="List of projects matching the query",
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
        description="True if completed projects were excluded from results",
    )


class ProjectBulkCreateResponse(BaseModel):
    """Response model for bulk project creation with partial success support."""

    created: list[ProjectResponse] = Field(
        default_factory=list,
        description="Successfully created projects",
    )
    failed: list[BulkCreateFailure] = Field(
        default_factory=list,
        description="Projects that failed to create with error details",
    )
