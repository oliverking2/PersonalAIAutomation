"""Pydantic models for memory API endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.agent.enums import MemoryCategory


class CreateMemoryRequest(BaseModel):
    """Request model for creating a memory."""

    content: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="The fact or information to remember",
    )
    category: MemoryCategory = Field(
        ...,
        description="Category of memory: person, preference, context, or project",
    )
    subject: str | None = Field(
        None,
        max_length=200,
        description="Optional subject/entity this memory relates to",
    )


class UpdateMemoryRequest(BaseModel):
    """Request model for updating a memory."""

    content: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="The updated content for this memory",
    )
    subject: str | None = Field(
        None,
        max_length=200,
        description="Optional updated subject/entity (use when the subject itself changes)",
    )


class MemoryResponse(BaseModel):
    """Response model for a single memory."""

    id: str = Field(..., description="8-character memory ID")
    category: MemoryCategory = Field(..., description="Memory category")
    subject: str | None = Field(None, description="Optional subject/entity")
    content: str = Field(..., description="Current version content")
    version: int = Field(..., description="Current version number")
    created_at: datetime = Field(..., description="When memory was created")
    updated_at: datetime | None = Field(
        None,
        description="When memory was last updated (from latest version)",
    )


class MemoryVersionResponse(BaseModel):
    """Response model for a memory version."""

    version_number: int = Field(..., description="Version number")
    content: str = Field(..., description="Content at this version")
    created_at: datetime = Field(..., description="When this version was created")
    source_conversation_id: str | None = Field(
        None,
        description="Source conversation ID if tracked",
    )


class MemoryWithHistoryResponse(BaseModel):
    """Response model for a memory with its version history."""

    id: str = Field(..., description="8-character memory ID")
    category: MemoryCategory = Field(..., description="Memory category")
    subject: str | None = Field(None, description="Optional subject/entity")
    created_at: datetime = Field(..., description="When memory was created")
    versions: list[MemoryVersionResponse] = Field(
        ...,
        description="All versions of this memory",
    )


class MemoryListResponse(BaseModel):
    """Response model for listing memories."""

    memories: list[MemoryResponse] = Field(..., description="List of memories")
    total: int = Field(..., description="Total number of memories")
