"""Common Notion models."""

from datetime import date

from pydantic import BaseModel, Field


class PageResponse(BaseModel):
    """Response model for page endpoints."""

    id: str = Field(..., description="Page ID")
    task_name: str = Field(..., description="Task title")
    status: str | None = Field(None, description="Task status")
    due_date: date | None = Field(None, description="Task due date")
    priority: str | None = Field(None, description="Task priority")


class QueryResponse(BaseModel):
    """Response model for data source query endpoint."""

    results: list[PageResponse] = Field(
        default_factory=list,
        description="List of all pages matching the query",
    )
