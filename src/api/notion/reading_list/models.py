"""Pydantic models for Reading List API endpoints."""

from datetime import date

from pydantic import BaseModel, Field

from src.api.notion.common.models import BulkCreateFailure
from src.api.notion.common.utils import FuzzyMatchQuality
from src.notion.enums import Priority, ReadingCategory, ReadingStatus, ReadingType


class ReadingItemResponse(BaseModel):
    """Response model for reading item endpoints."""

    id: str = Field(..., description="Reading item page ID")
    title: str = Field(..., description="Reading item title")
    item_type: str = Field(..., description="Type of reading item (Book, Article, Other)")
    status: str | None = Field(None, description="Reading status")
    priority: str | None = Field(None, description="Reading priority")
    category: str | None = Field(None, description="Reading category")
    item_url: str | None = Field(None, description="URL of the article/book")
    content: str | None = Field(None, description="Page content in markdown format")


class ReadingItemCreateRequest(BaseModel):
    """Request model for reading item creation with validated enum fields."""

    title: str = Field(..., min_length=1, description="Reading item title")
    item_type: ReadingType = Field(
        ..., description=f"Type of reading item ({', '.join(ReadingType)})"
    )
    status: ReadingStatus | None = Field(
        default=ReadingStatus.TO_READ,
        description=f"Reading status (default: {ReadingStatus.TO_READ}) ({', '.join(ReadingStatus)})",
    )
    priority: Priority | None = Field(None, description=f"Reading priority ({', '.join(Priority)})")
    category: ReadingCategory | None = Field(
        None, description=f"Reading category ({', '.join(ReadingCategory)})"
    )
    item_url: str | None = Field(None, description="URL of the article/book")
    content: str | None = Field(None, description="Markdown content for the reading item page body")


class ReadingItemUpdateRequest(BaseModel):
    """Request model for reading item update with validated enum fields."""

    title: str | None = Field(None, min_length=1, description="Reading item title")
    item_type: ReadingType | None = Field(
        None, description=f"Type of reading item ({', '.join(ReadingType)})"
    )
    status: ReadingStatus | None = Field(
        None, description=f"Reading status ({', '.join(ReadingStatus)})"
    )
    priority: Priority | None = Field(None, description=f"Reading priority ({', '.join(Priority)})")
    category: ReadingCategory | None = Field(
        None, description=f"Reading category ({', '.join(ReadingCategory)})"
    )
    item_url: str | None = Field(None, description="URL of the article/book")
    content: str | None = Field(
        None, description="Markdown content to replace page body (if provided)"
    )


class ReadingQueryRequest(BaseModel):
    """Request model for reading query endpoint with structured filters."""

    name_filter: str | None = Field(
        None, description="Fuzzy match against item title (returns top 5 matches)"
    )
    include_completed: bool = Field(
        False, description="Whether to include completed items (default: exclude)"
    )
    item_type: ReadingType | None = Field(
        None, description=f"Filter by reading type ({', '.join(ReadingType)})"
    )
    status: ReadingStatus | None = Field(
        None, description=f"Filter by reading status ({', '.join(ReadingStatus)})"
    )
    category: ReadingCategory | None = Field(
        None,
        description=f"Filter by category ({', '.join(ReadingCategory)})",
    )
    priority: Priority | None = Field(
        None, description=f"Filter by priority ({', '.join(Priority)})"
    )
    edited_before: date | None = Field(
        None, description="Filter items last edited before this date (for finding stale items)"
    )
    edited_after: date | None = Field(None, description="Filter items last edited after this date")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of items to return")


class ReadingQueryResponse(BaseModel):
    """Response model for reading query endpoint."""

    results: list[ReadingItemResponse] = Field(
        default_factory=list,
        description="List of reading items matching the query",
    )
    fuzzy_match_quality: FuzzyMatchQuality | None = Field(
        None,
        description=(
            "Quality of fuzzy name match: None=unfiltered, "
            "'good'=best match score >= 60, 'weak'=no matches above threshold"
        ),
    )
    excluded_completed: bool = Field(
        False,
        description="True if completed items were excluded from results",
    )


class ReadingBulkCreateResponse(BaseModel):
    """Response model for bulk reading item creation with partial success support."""

    created: list[ReadingItemResponse] = Field(
        default_factory=list,
        description="Successfully created reading items",
    )
    failed: list[BulkCreateFailure] = Field(
        default_factory=list,
        description="Reading items that failed to create with error details",
    )
