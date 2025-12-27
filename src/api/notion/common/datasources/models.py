"""Pydantic models for Notion API endpoints."""

from typing import Any

from pydantic import BaseModel, Field


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
