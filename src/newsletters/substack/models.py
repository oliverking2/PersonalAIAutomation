"""Pydantic models for Substack processing."""

from datetime import datetime

from pydantic import BaseModel, Field


class SubstackProcessingResult(BaseModel):
    """Result of processing Substack publications."""

    posts_processed: int = 0
    posts_new: int = 0
    posts_duplicate: int = 0
    errors: list[str] = Field(default_factory=list)
    latest_published_at: datetime | None = None
