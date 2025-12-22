"""Pydantic models for Notion API endpoints."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

# Database models


class DatabaseResponse(BaseModel):
    """Response model for database retrieval endpoint."""

    id: str = Field(..., description="Database ID")
    title: str = Field(..., description="Database title")
    properties: dict[str, Any] = Field(..., description="Property schema definitions")


# Data source models


class DataSourceResponse(BaseModel):
    """Response model for data source retrieval endpoint."""

    id: str = Field(..., description="Data source ID")
    database_id: str = Field(..., description="Parent database ID")
    properties: dict[str, Any] = Field(..., description="Property schema definitions")


class QueryRequest(BaseModel):
    """Request model for data source query endpoint."""

    filter: dict[str, Any] | None = Field(
        None,
        description="Notion filter object",
    )
    sorts: list[dict[str, Any]] | None = Field(
        None,
        description="List of sort objects",
    )


class TemplatesResponse(BaseModel):
    """Response model for data source templates endpoint."""

    templates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of available templates",
    )


# Page models


class PageResponse(BaseModel):
    """Response model for page endpoints."""

    id: str = Field(..., description="Page ID")
    task_name: str = Field(..., description="Task title")
    status: str | None = Field(None, description="Task status")
    due_date: date | None = Field(None, description="Task due date")
    priority: str | None = Field(None, description="Task priority")
    url: str = Field(..., description="Notion page URL")


class PageCreateRequest(BaseModel):
    """Request model for page creation endpoint."""

    data_source_id: str = Field(..., description="Parent data source ID")
    task_name: str = Field(..., min_length=1, description="Task title")
    status: str | None = Field(None, description="Initial task status")
    due_date: date | None = Field(None, description="Task due date")


class PageUpdateRequest(BaseModel):
    """Request model for page update endpoint."""

    status: str | None = Field(None, description="New task status")
    due_date: date | None = Field(None, description="New due date")


class QueryResponse(BaseModel):
    """Response model for data source query endpoint."""

    results: list[PageResponse] = Field(
        default_factory=list,
        description="List of all pages matching the query",
    )
