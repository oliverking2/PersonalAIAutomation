"""Pydantic models for API responses."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""

    detail: str = Field(..., description="Error description")
