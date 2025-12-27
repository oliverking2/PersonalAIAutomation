"""Pydantic models for Notion API endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class DatabaseResponse(BaseModel):
    """Response model for database retrieval endpoint."""

    id: str = Field(..., description="Database ID")
    title: str = Field(..., description="Database title")
    properties: dict[str, Any] = Field(..., description="Property schema definitions")
