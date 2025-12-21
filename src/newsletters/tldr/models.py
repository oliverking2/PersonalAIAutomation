"""Pydantic models for parsed newsletter data."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class NewsletterType(StrEnum):
    """Type of TLDR newsletter."""

    TLDR = "tldr"
    TLDR_AI = "tldr_ai"
    TLDR_DEV = "tldr_dev"


class ParsedArticle(BaseModel):
    """An article extracted from a TLDR newsletter."""

    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    description: str | None = None
    section: str | None = Field(None, max_length=2000)
    source_publication: str | None = Field(None, max_length=200)


class ParsedNewsletter(BaseModel):
    """A parsed TLDR newsletter with extracted articles."""

    email_id: str = Field(..., min_length=1)
    newsletter_type: NewsletterType
    subject: str = Field(..., min_length=1, max_length=500)
    received_at: datetime
    articles: list[ParsedArticle]
