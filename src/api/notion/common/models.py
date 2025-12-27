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


class BulkCreateFailure(BaseModel):
    """Details of a failed item in bulk creation."""

    name: str = Field(..., description="Name/title of the item that failed")
    error: str = Field(..., description="Error message describing why creation failed")
