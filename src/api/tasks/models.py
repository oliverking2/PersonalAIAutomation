"""Pydantic models for task trigger endpoints."""

from pydantic import BaseModel, Field


class TaskTriggerRequest(BaseModel):
    """Request model for triggering newsletter processing task."""

    days_back: int = Field(
        default=1,
        ge=1,
        le=30,
        description="Number of days to look back for newsletters",
    )


class TaskTriggerResponse(BaseModel):
    """Response model for triggered task."""

    task_id: str = Field(..., description="Celery task identifier")
    task_name: str = Field(..., description="Name of the triggered task")
    status: str = Field(..., description="Task submission status")


class TaskStatusResponse(BaseModel):
    """Response model for task status query."""

    task_id: str = Field(..., description="Celery task identifier")
    status: str = Field(..., description="Task status (PENDING, STARTED, SUCCESS, FAILURE)")
    result: dict[str, int | list[str]] | None = Field(
        default=None, description="Task result if completed"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""

    detail: str = Field(..., description="Error description")
