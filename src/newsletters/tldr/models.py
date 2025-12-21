"""Pydantic models for parsed newsletter data."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class NewsletterType(StrEnum):
    """Type of TLDR newsletter."""

    TLDR = "TLDR"
    TLDR_AI = "TLDR AI"
    TLDR_DEV = "TLDR Dev"
    TLDR_DATA = "TLDR Data"


class ParsedArticle(BaseModel):
    """An article extracted from a TLDR newsletter."""

    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    url_parsed: HttpUrl
    description: str | None = None


class ParsedNewsletter(BaseModel):
    """A parsed TLDR newsletter with extracted articles."""

    email_id: str = Field(..., min_length=1)
    newsletter_type: NewsletterType
    subject: str = Field(..., min_length=1, max_length=500)
    received_at: datetime
    articles: list[ParsedArticle]
