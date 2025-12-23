"""Pydantic models for Notion API endpoints."""

from datetime import date

from pydantic import BaseModel, Field


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
