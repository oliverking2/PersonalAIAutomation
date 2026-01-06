"""API endpoints for managing user reminders."""

import logging
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.reminders.models import (
    AcknowledgeResponse,
    CreateReminderRequest,
    QueryRemindersRequest,
    QueryRemindersResponse,
    ReminderScheduleResponse,
    SnoozeRequest,
    SnoozeResponse,
)
from src.database.connection import get_session
from src.database.reminders import (
    ReminderSchedule,
    ReminderStatus,
    acknowledge_instance,
    create_reminder_instance,
    create_reminder_schedule,
    deactivate_schedule,
    get_active_instance_for_schedule,
    get_instance_by_id,
    get_schedule_by_id,
    list_schedules_for_chat,
    snooze_instance,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reminders", tags=["Reminders"])


def _get_chat_id() -> int:
    """Get the configured Telegram chat ID.

    :returns: The chat ID.
    :raises HTTPException: If not configured.
    """
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TELEGRAM_CHAT_ID not configured",
        )
    return int(chat_id)


def _schedule_to_response(schedule: ReminderSchedule) -> ReminderScheduleResponse:
    """Convert a schedule model to response.

    :param schedule: The database model.
    :returns: API response model.
    """
    return ReminderScheduleResponse(
        id=schedule.id,
        message=schedule.message,
        chat_id=schedule.chat_id,
        cron_schedule=schedule.cron_schedule,
        next_trigger_at=schedule.next_trigger_at,
        is_active=schedule.is_active,
        is_recurring=schedule.is_recurring,
        created_at=schedule.created_at,
    )


@router.post(
    "",
    response_model=ReminderScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create reminder",
)
def create_reminder(request: CreateReminderRequest) -> ReminderScheduleResponse:
    """Create a new reminder.

    Creates a reminder schedule and its first instance. For one-time reminders,
    the schedule is deactivated after the instance is resolved. For recurring
    reminders, a new instance is created each time the schedule triggers.
    """
    start = time.perf_counter()
    chat_id = _get_chat_id()

    logger.info(
        f"Create reminder: message={request.message[:50]!r}..., "
        f"trigger_at={request.trigger_at}, cron={request.cron_schedule}"
    )

    with get_session() as session:
        # Create the schedule
        schedule = create_reminder_schedule(
            session=session,
            message=request.message,
            chat_id=chat_id,
            trigger_at=request.trigger_at,
            cron_schedule=request.cron_schedule,
        )

        # Create the first instance
        create_reminder_instance(
            session=session,
            schedule=schedule,
            trigger_at=request.trigger_at,
        )

        response = _schedule_to_response(schedule)

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Create reminder complete: id={response.id}, "
        f"recurring={response.is_recurring}, elapsed={elapsed_ms:.0f}ms"
    )

    return response


@router.post(
    "/query",
    response_model=QueryRemindersResponse,
    summary="Query reminders",
)
def query_reminders(request: QueryRemindersRequest) -> QueryRemindersResponse:
    """Query reminder schedules.

    Returns reminder schedules for the configured chat. By default, only
    active schedules are returned.
    """
    start = time.perf_counter()
    chat_id = _get_chat_id()

    logger.info(
        f"Query reminders: chat_id={chat_id}, "
        f"include_inactive={request.include_inactive}, limit={request.limit}"
    )

    with get_session() as session:
        schedules = list_schedules_for_chat(
            session=session,
            chat_id=chat_id,
            include_inactive=request.include_inactive,
            limit=request.limit,
        )
        results = [_schedule_to_response(s) for s in schedules]

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Query reminders complete: found={len(results)}, elapsed={elapsed_ms:.0f}ms")

    return QueryRemindersResponse(results=results)


@router.get(
    "/{reminder_id}",
    response_model=ReminderScheduleResponse,
    summary="Get reminder",
)
def get_reminder(reminder_id: UUID) -> ReminderScheduleResponse:
    """Get a specific reminder schedule by ID."""
    start = time.perf_counter()
    logger.info(f"Get reminder: id={reminder_id}")

    with get_session() as session:
        schedule = get_schedule_by_id(session, reminder_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reminder not found: {reminder_id}",
            )
        response = _schedule_to_response(schedule)

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Get reminder complete: id={reminder_id}, elapsed={elapsed_ms:.0f}ms")

    return response


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel reminder",
)
def cancel_reminder(reminder_id: UUID) -> None:
    """Cancel (deactivate) a reminder schedule.

    The schedule and its instances are kept for history but will no longer
    trigger new instances or send messages.
    """
    start = time.perf_counter()
    logger.info(f"Cancel reminder: id={reminder_id}")

    with get_session() as session:
        schedule = deactivate_schedule(session, reminder_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reminder not found: {reminder_id}",
            )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"Cancel reminder complete: id={reminder_id}, elapsed={elapsed_ms:.0f}ms")


@router.post(
    "/{reminder_id}/acknowledge",
    response_model=AcknowledgeResponse,
    summary="Acknowledge reminder",
)
def acknowledge_reminder(reminder_id: UUID) -> AcknowledgeResponse:
    """Acknowledge a reminder.

    Marks the active instance as acknowledged. For one-time reminders, this
    deactivates the schedule. For recurring reminders, the schedule remains
    active and will create a new instance at the next trigger time.
    """
    start = time.perf_counter()
    logger.info(f"Acknowledge reminder: schedule_id={reminder_id}")

    with get_session() as session:
        schedule = get_schedule_by_id(session, reminder_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reminder not found: {reminder_id}",
            )

        # Find the active instance for this schedule
        instance = get_active_instance_for_schedule(session, reminder_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active instance to acknowledge",
            )

        # Acknowledge the instance
        now = datetime.now(UTC)
        acknowledged = acknowledge_instance(session, instance.id, now)
        if acknowledged is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to acknowledge instance",
            )

        # For one-time reminders, deactivate the schedule
        if not schedule.is_recurring:
            deactivate_schedule(session, reminder_id)

        response = AcknowledgeResponse(
            instance_id=instance.id,
            schedule_id=reminder_id,
            acknowledged_at=now,
            is_recurring=schedule.is_recurring,
            next_trigger_at=schedule.next_trigger_at if schedule.is_recurring else None,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Acknowledge reminder complete: schedule_id={reminder_id}, "
        f"instance_id={instance.id}, elapsed={elapsed_ms:.0f}ms"
    )

    return response


@router.post(
    "/{reminder_id}/snooze",
    response_model=SnoozeResponse,
    summary="Snooze reminder",
)
def snooze_reminder_endpoint(reminder_id: UUID, request: SnoozeRequest) -> SnoozeResponse:
    """Snooze a reminder for a specified duration.

    Delays the active instance from re-sending until the snooze period ends.
    The instance will resume sending at the snoozed_until time.
    """
    start = time.perf_counter()
    logger.info(
        f"Snooze reminder: schedule_id={reminder_id}, duration_minutes={request.duration_minutes}"
    )

    with get_session() as session:
        schedule = get_schedule_by_id(session, reminder_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reminder not found: {reminder_id}",
            )

        # Find the active instance for this schedule
        instance = get_active_instance_for_schedule(session, reminder_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active instance to snooze",
            )

        # Snooze the instance
        snooze_until = datetime.now(UTC) + timedelta(minutes=request.duration_minutes)
        snoozed = snooze_instance(session, instance.id, snooze_until)
        if snoozed is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to snooze instance",
            )

        response = SnoozeResponse(
            instance_id=instance.id,
            snoozed_until=snooze_until,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Snooze reminder complete: schedule_id={reminder_id}, "
        f"instance_id={instance.id}, snoozed_until={snooze_until}, elapsed={elapsed_ms:.0f}ms"
    )

    return response


@router.post(
    "/instances/{instance_id}/acknowledge",
    response_model=AcknowledgeResponse,
    summary="Acknowledge instance",
)
def acknowledge_instance_endpoint(instance_id: UUID) -> AcknowledgeResponse:
    """Acknowledge a specific reminder instance by its ID.

    This endpoint is used by Telegram callback handlers to acknowledge
    a reminder directly by instance ID (from the callback data).
    """
    start = time.perf_counter()
    logger.info(f"Acknowledge instance: instance_id={instance_id}")

    with get_session() as session:
        instance = get_instance_by_id(session, instance_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instance not found: {instance_id}",
            )

        # Check if already resolved
        if instance.status in [ReminderStatus.ACKNOWLEDGED.value, ReminderStatus.EXPIRED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Instance already resolved: status={instance.status}",
            )

        schedule = instance.schedule

        # Acknowledge the instance
        now = datetime.now(UTC)
        acknowledged = acknowledge_instance(session, instance_id, now)
        if acknowledged is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to acknowledge instance",
            )

        # For one-time reminders, deactivate the schedule
        if not schedule.is_recurring:
            deactivate_schedule(session, schedule.id)

        response = AcknowledgeResponse(
            instance_id=instance_id,
            schedule_id=schedule.id,
            acknowledged_at=now,
            is_recurring=schedule.is_recurring,
            next_trigger_at=schedule.next_trigger_at if schedule.is_recurring else None,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Acknowledge instance complete: instance_id={instance_id}, elapsed={elapsed_ms:.0f}ms"
    )

    return response


@router.post(
    "/instances/{instance_id}/snooze",
    response_model=SnoozeResponse,
    summary="Snooze instance",
)
def snooze_instance_endpoint(instance_id: UUID, request: SnoozeRequest) -> SnoozeResponse:
    """Snooze a specific reminder instance by its ID.

    This endpoint is used by Telegram callback handlers to snooze
    a reminder directly by instance ID (from the callback data).
    """
    start = time.perf_counter()
    logger.info(
        f"Snooze instance: instance_id={instance_id}, duration_minutes={request.duration_minutes}"
    )

    with get_session() as session:
        instance = get_instance_by_id(session, instance_id)
        if instance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instance not found: {instance_id}",
            )

        # Check if already resolved
        if instance.status in [ReminderStatus.ACKNOWLEDGED.value, ReminderStatus.EXPIRED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Instance already resolved: status={instance.status}",
            )

        # Snooze the instance
        snooze_until = datetime.now(UTC) + timedelta(minutes=request.duration_minutes)
        snoozed = snooze_instance(session, instance_id, snooze_until)
        if snoozed is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to snooze instance",
            )

        response = SnoozeResponse(
            instance_id=instance_id,
            snoozed_until=snooze_until,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"Snooze instance complete: instance_id={instance_id}, "
        f"snoozed_until={snooze_until}, elapsed={elapsed_ms:.0f}ms"
    )

    return response
