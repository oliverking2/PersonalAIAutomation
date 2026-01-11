"""Pydantic models for reminders API endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.database.reminders.models import ReminderStatus


class ReminderScheduleResponse(BaseModel):
    """Response model for reminder schedules."""

    id: UUID = Field(..., description="Schedule ID")
    message: str = Field(..., description="Reminder message")
    chat_id: int = Field(..., description="Telegram chat ID")
    cron_schedule: str | None = Field(None, description="Cron expression for recurring reminders")
    next_trigger_at: datetime = Field(..., description="Next scheduled trigger time")
    is_active: bool = Field(..., description="Whether the schedule is active")
    is_recurring: bool = Field(..., description="Whether this is a recurring reminder")
    created_at: datetime = Field(..., description="When the schedule was created")


class ReminderInstanceResponse(BaseModel):
    """Response model for reminder instances."""

    id: UUID = Field(..., description="Instance ID")
    schedule_id: UUID = Field(..., description="Parent schedule ID")
    status: ReminderStatus = Field(..., description="Current status")
    send_count: int = Field(..., description="Number of times sent")
    max_sends: int = Field(..., description="Maximum send attempts")
    next_send_at: datetime = Field(..., description="Next send time")
    snoozed_until: datetime | None = Field(None, description="Snoozed until this time")
    acknowledged_at: datetime | None = Field(None, description="When acknowledged")
    expired_at: datetime | None = Field(None, description="When expired")
    created_at: datetime = Field(..., description="When the instance was created")
    message: str = Field(..., description="Reminder message (from schedule)")


class CreateReminderRequest(BaseModel):
    """Request model for creating a reminder."""

    message: str = Field(..., min_length=1, max_length=500, description="Reminder message")
    trigger_at: datetime = Field(..., description="When to trigger (ISO format with timezone)")
    cron_schedule: str | None = Field(
        None,
        description="Cron expression for recurring reminders (NULL for one-time)",
    )


class QueryRemindersRequest(BaseModel):
    """Request model for querying reminders."""

    include_inactive: bool = Field(
        False,
        description="Include deactivated schedules",
    )
    limit: int = Field(20, ge=1, le=100, description="Maximum schedules to return")


class UpdateReminderRequest(BaseModel):
    """Request model for updating a reminder."""

    message: str | None = Field(
        None,
        min_length=1,
        max_length=500,
        description="New reminder message",
    )
    trigger_at: datetime | None = Field(
        None,
        description="New trigger time (ISO format with timezone)",
    )
    cron_schedule: str | None = Field(
        None,
        description="New cron schedule (empty string to convert to one-time)",
    )


class QueryRemindersResponse(BaseModel):
    """Response model for querying reminders."""

    results: list[ReminderScheduleResponse] = Field(
        default_factory=list,
        description="List of reminder schedules",
    )


class SnoozeRequest(BaseModel):
    """Request model for snoozing a reminder."""

    duration_minutes: int = Field(
        60,
        ge=5,
        le=1440,
        description="Snooze duration in minutes (5 to 1440)",
    )


class AcknowledgeResponse(BaseModel):
    """Response model for acknowledging a reminder."""

    instance_id: UUID = Field(..., description="Acknowledged instance ID")
    schedule_id: UUID = Field(..., description="Parent schedule ID")
    acknowledged_at: datetime = Field(..., description="When acknowledged")
    is_recurring: bool = Field(..., description="Whether this is a recurring reminder")
    next_trigger_at: datetime | None = Field(
        None,
        description="Next trigger time for recurring reminders",
    )


class SnoozeResponse(BaseModel):
    """Response model for snoozing a reminder."""

    instance_id: UUID = Field(..., description="Snoozed instance ID")
    snoozed_until: datetime = Field(..., description="Snoozed until this time")
