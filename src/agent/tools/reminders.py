"""Reminders tool configuration for the AI agent.

This module defines tools for managing reminders. Unlike other domains,
reminders have a simpler interface:
- Single-item creation (not bulk)
- Cancel via DELETE (not update)
- Query for listing active reminders
"""

import logging
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, Field

from src.agent.enums import RiskLevel
from src.agent.models import ToolDef
from src.api.client import InternalAPIClient

logger = logging.getLogger(__name__)


class CreateReminderArgs(BaseModel):
    """Arguments for creating a reminder."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The reminder message to send",
    )
    trigger_at: datetime = Field(
        ...,
        description=(
            "When to trigger the reminder (ISO 8601 format with timezone, "
            "e.g. '2024-01-15T09:00:00Z' or '2024-01-15T09:00:00+00:00')"
        ),
    )
    cron_schedule: str | None = Field(
        None,
        description=(
            "Cron expression for recurring reminders (e.g. '0 9 * * *' for daily at 9am). "
            "Leave empty for one-time reminders."
        ),
    )


class QueryRemindersArgs(BaseModel):
    """Arguments for querying reminders."""

    include_inactive: bool = Field(
        False,
        description="Include cancelled/completed reminders in results",
    )
    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of reminders to return",
    )


class CancelReminderArgs(BaseModel):
    """Arguments for cancelling a reminder."""

    reminder_id: str = Field(
        ...,
        min_length=1,
        description="The ID of the reminder to cancel",
    )


class UpdateReminderArgs(BaseModel):
    """Arguments for updating a reminder."""

    reminder_id: str = Field(
        ...,
        min_length=1,
        description="The ID of the reminder to update",
    )
    message: str | None = Field(
        None,
        min_length=1,
        max_length=500,
        description="New reminder message",
    )
    trigger_at: datetime | None = Field(
        None,
        description=(
            "New trigger time (ISO 8601 format with timezone, "
            "e.g. '2024-01-15T09:00:00Z' or '2024-01-15T09:00:00+00:00')"
        ),
    )
    cron_schedule: str | None = Field(
        None,
        description=(
            "New cron schedule (e.g. '0 9 * * 2' for Tuesday at 9am). "
            "Set to empty string to convert a recurring reminder to one-time."
        ),
    )


def _get_client() -> InternalAPIClient:
    """Get an API client instance.

    :returns: Configured API client.
    """
    return InternalAPIClient()


def _create_reminder_handler(args: BaseModel) -> dict[str, Any]:
    """Handle reminder creation.

    :param args: CreateReminderArgs instance.
    :returns: Created reminder details.
    """
    create_args = cast(CreateReminderArgs, args)
    logger.debug(f"Creating reminder: message={create_args.message[:50]!r}...")

    with _get_client() as client:
        response = cast(
            dict[str, Any],
            client.post(
                "/reminders",
                json=args.model_dump(mode="json", exclude_none=True),
            ),
        )

    return {
        "id": response.get("id"),
        "message": response.get("message"),
        "next_trigger_at": response.get("next_trigger_at"),
        "is_recurring": response.get("is_recurring"),
        "created": True,
    }


def _query_reminders_handler(args: BaseModel) -> dict[str, Any]:
    """Handle reminder query.

    :param args: QueryRemindersArgs instance.
    :returns: List of reminders.
    """
    logger.debug("Querying reminders")

    with _get_client() as client:
        response = cast(
            dict[str, Any],
            client.post(
                "/reminders/query",
                json=args.model_dump(mode="json", exclude_none=True),
            ),
        )

    results = response.get("results", [])
    # Filter to essential fields for LLM context
    filtered = [
        {
            "id": r.get("id"),
            "message": r.get("message"),
            "next_trigger_at": r.get("next_trigger_at"),
            "cron_schedule": r.get("cron_schedule"),
            "is_recurring": r.get("is_recurring"),
            "is_active": r.get("is_active"),
        }
        for r in results
    ]

    return {"reminders": filtered, "count": len(filtered)}


def _cancel_reminder_handler(args: BaseModel) -> dict[str, Any]:
    """Handle reminder cancellation.

    :param args: CancelReminderArgs instance.
    :returns: Cancellation confirmation.
    """
    cancel_args = cast(CancelReminderArgs, args)
    logger.debug(f"Cancelling reminder: id={cancel_args.reminder_id}")

    with _get_client() as client:
        client.delete(f"/reminders/{cancel_args.reminder_id}")

    return {
        "reminder_id": cancel_args.reminder_id,
        "cancelled": True,
    }


def _update_reminder_handler(args: BaseModel) -> dict[str, Any]:
    """Handle reminder update.

    :param args: UpdateReminderArgs instance.
    :returns: Updated reminder details.
    """
    update_args = cast(UpdateReminderArgs, args)
    logger.debug(f"Updating reminder: id={update_args.reminder_id}")

    # Build the update payload, only including provided fields
    payload: dict[str, Any] = {}
    if update_args.message is not None:
        payload["message"] = update_args.message
    if update_args.trigger_at is not None:
        payload["trigger_at"] = update_args.trigger_at.isoformat()
    if update_args.cron_schedule is not None:
        payload["cron_schedule"] = update_args.cron_schedule

    with _get_client() as client:
        response = client.patch(
            f"/reminders/{update_args.reminder_id}",
            json=payload,
        )

    return {
        "id": response.get("id"),
        "message": response.get("message"),
        "next_trigger_at": response.get("next_trigger_at"),
        "cron_schedule": response.get("cron_schedule"),
        "is_recurring": response.get("is_recurring"),
        "updated": True,
    }


CREATE_REMINDER_TOOL = ToolDef(
    name="create_reminder",
    description=(
        "Create a reminder that will be sent via Telegram at the specified time. "
        "For one-time reminders, just provide message and trigger_at. "
        "For recurring reminders, also provide a cron_schedule (e.g. '0 9 * * 1-5' for "
        "weekdays at 9am). The trigger_at must be in ISO 8601 format with timezone."
    ),
    tags=frozenset({"domain:reminders", "reminders", "create"}),
    risk_level=RiskLevel.SAFE,
    args_model=CreateReminderArgs,
    handler=_create_reminder_handler,
)

QUERY_REMINDERS_TOOL = ToolDef(
    name="query_reminders",
    description=(
        "Query active reminders. By default returns only active reminders; "
        "set include_inactive=true to include cancelled or completed reminders. "
        "Returns reminder ID, message, next trigger time, and whether it's recurring."
    ),
    tags=frozenset({"domain:reminders", "reminders", "query", "list"}),
    risk_level=RiskLevel.SAFE,
    args_model=QueryRemindersArgs,
    handler=_query_reminders_handler,
)

CANCEL_REMINDER_TOOL = ToolDef(
    name="cancel_reminder",
    description=(
        "Cancel, delete, or remove a reminder by its ID. Stops the reminder from "
        "triggering or sending any more messages. Use query_reminders first to find "
        "the reminder ID if you don't have it."
    ),
    tags=frozenset({"domain:reminders", "reminders", "cancel", "delete", "remove"}),
    risk_level=RiskLevel.SENSITIVE,
    args_model=CancelReminderArgs,
    handler=_cancel_reminder_handler,
)

UPDATE_REMINDER_TOOL = ToolDef(
    name="update_reminder",
    description=(
        "Update an existing reminder's message, schedule, or trigger time. "
        "You can update any combination of: message (the reminder text), "
        "trigger_at (when it triggers), or cron_schedule (the recurrence pattern). "
        "To convert a recurring reminder to one-time, set cron_schedule to empty string. "
        "Use query_reminders first to find the reminder ID if you don't have it."
    ),
    tags=frozenset({"domain:reminders", "reminders", "update", "edit", "modify"}),
    risk_level=RiskLevel.SENSITIVE,
    args_model=UpdateReminderArgs,
    handler=_update_reminder_handler,
)


def get_reminders_tools() -> list[ToolDef]:
    """Get all reminder tool definitions.

    :returns: List of ToolDef instances for reminder operations.
    """
    return [
        CREATE_REMINDER_TOOL,
        QUERY_REMINDERS_TOOL,
        UPDATE_REMINDER_TOOL,
        CANCEL_REMINDER_TOOL,
    ]
