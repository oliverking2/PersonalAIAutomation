"""Base Pydantic models for newsletter processing."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class ParsedArticleBase(BaseModel):
    """Base model for a parsed article from any newsletter source."""

    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    description: str | None = None


class ParsedDigestBase(BaseModel):
    """Base model for a parsed newsletter/digest."""

    email_id: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1, max_length=500)
    received_at: datetime


class ProcessingResult(BaseModel):
    """Result of processing newsletters/digests."""

    digests_processed: int = 0
    articles_extracted: int = 0
    articles_new: int = 0
    articles_duplicate: int = 0
    errors: list[str] = Field(default_factory=list)
    latest_received_at: datetime | None = None
