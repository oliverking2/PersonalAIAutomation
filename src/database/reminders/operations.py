"""Database operations for user reminders."""

from __future__ import annotations

import logging
import uuid as uuid_module
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.database.reminders.models import ReminderInstance, ReminderSchedule, ReminderStatus

logger = logging.getLogger(__name__)

# Default interval between re-sends (in minutes)
RESEND_INTERVAL_MINUTES = 30


def create_reminder_schedule(
    session: Session,
    message: str,
    chat_id: int,
    trigger_at: datetime,
    cron_schedule: str | None = None,
) -> ReminderSchedule:
    """Create a new reminder schedule.

    :param session: Database session.
    :param message: The reminder message.
    :param chat_id: Telegram chat ID.
    :param trigger_at: When the reminder should first trigger.
    :param cron_schedule: Optional cron expression for recurring reminders.
    :returns: The created schedule.
    """
    schedule = ReminderSchedule(
        message=message,
        chat_id=chat_id,
        next_trigger_at=trigger_at,
        cron_schedule=cron_schedule,
    )
    session.add(schedule)
    session.flush()
    logger.info(
        f"Created reminder schedule: id={schedule.id}, "
        f"recurring={schedule.is_recurring}, trigger_at={trigger_at}"
    )
    return schedule


def create_reminder_instance(
    session: Session,
    schedule: ReminderSchedule,
    trigger_at: datetime,
) -> ReminderInstance:
    """Create a new reminder instance when a schedule triggers.

    :param session: Database session.
    :param schedule: The parent schedule.
    :param trigger_at: When the reminder should be sent.
    :returns: The created instance.
    """
    instance = ReminderInstance(
        schedule_id=schedule.id,
        next_send_at=trigger_at,
    )
    session.add(instance)
    session.flush()
    logger.info(f"Created reminder instance: id={instance.id}, schedule_id={schedule.id}")
    return instance


def get_schedule_by_id(
    session: Session,
    schedule_id: uuid_module.UUID,
) -> ReminderSchedule | None:
    """Get a reminder schedule by ID.

    :param session: Database session.
    :param schedule_id: Schedule ID.
    :returns: The schedule or None if not found.
    """
    return session.query(ReminderSchedule).filter(ReminderSchedule.id == schedule_id).first()


def get_instance_by_id(
    session: Session,
    instance_id: uuid_module.UUID,
) -> ReminderInstance | None:
    """Get a reminder instance by ID.

    :param session: Database session.
    :param instance_id: Instance ID.
    :returns: The instance or None if not found.
    """
    return session.query(ReminderInstance).filter(ReminderInstance.id == instance_id).first()


def get_schedules_to_trigger(
    session: Session,
    now: datetime | None = None,
) -> list[ReminderSchedule]:
    """Get active schedules that are due to trigger.

    Used by the Dagster job to find schedules that need new instances created.

    :param session: Database session.
    :param now: Current time (defaults to now).
    :returns: List of schedules ready to trigger.
    """
    if now is None:
        now = datetime.now(UTC)

    return (
        session.query(ReminderSchedule)
        .filter(
            ReminderSchedule.is_active.is_(True),
            ReminderSchedule.next_trigger_at <= now,
        )
        .all()
    )


def get_instances_to_send(
    session: Session,
    now: datetime | None = None,
) -> list[ReminderInstance]:
    """Get instances that are due to be sent.

    Returns instances that are:
    - PENDING and next_send_at <= now
    - ACTIVE and next_send_at <= now (re-sends)
    - SNOOZED and snoozed_until <= now

    :param session: Database session.
    :param now: Current time (defaults to now).
    :returns: List of instances ready to send.
    """
    if now is None:
        now = datetime.now(UTC)

    return (
        session.query(ReminderInstance)
        .filter(
            or_(
                # Pending instances ready to send
                and_(
                    ReminderInstance.status == ReminderStatus.PENDING.value,
                    ReminderInstance.next_send_at <= now,
                ),
                # Active instances ready for re-send
                and_(
                    ReminderInstance.status == ReminderStatus.ACTIVE.value,
                    ReminderInstance.next_send_at <= now,
                ),
                # Snoozed instances that are ready
                and_(
                    ReminderInstance.status == ReminderStatus.SNOOZED.value,
                    ReminderInstance.snoozed_until <= now,
                ),
            )
        )
        .all()
    )


def mark_instance_sent(
    session: Session,
    instance: ReminderInstance,
    now: datetime | None = None,
) -> None:
    """Mark an instance as sent and schedule next re-send.

    :param session: Database session.
    :param instance: The instance that was sent.
    :param now: Current time (defaults to now).
    """
    if now is None:
        now = datetime.now(UTC)

    instance.status = ReminderStatus.ACTIVE.value
    instance.send_count += 1
    instance.last_sent_at = now
    instance.next_send_at = now + timedelta(minutes=RESEND_INTERVAL_MINUTES)
    instance.snoozed_until = None
    session.flush()
    logger.info(
        f"Marked instance sent: id={instance.id}, "
        f"send_count={instance.send_count}/{instance.max_sends}"
    )


def acknowledge_instance(
    session: Session,
    instance_id: uuid_module.UUID,
    now: datetime | None = None,
) -> ReminderInstance | None:
    """Acknowledge a reminder instance.

    :param session: Database session.
    :param instance_id: Instance ID to acknowledge.
    :param now: Current time (defaults to now).
    :returns: The acknowledged instance or None if not found.
    """
    if now is None:
        now = datetime.now(UTC)

    instance = get_instance_by_id(session, instance_id)
    if instance is None:
        return None

    instance.status = ReminderStatus.ACKNOWLEDGED.value
    instance.acknowledged_at = now
    session.flush()
    logger.info(f"Acknowledged instance: id={instance_id}")
    return instance


def snooze_instance(
    session: Session,
    instance_id: uuid_module.UUID,
    snooze_until: datetime,
) -> ReminderInstance | None:
    """Snooze a reminder instance until a specific time.

    :param session: Database session.
    :param instance_id: Instance ID to snooze.
    :param snooze_until: When to resume sending.
    :returns: The snoozed instance or None if not found.
    """
    instance = get_instance_by_id(session, instance_id)
    if instance is None:
        return None

    instance.status = ReminderStatus.SNOOZED.value
    instance.snoozed_until = snooze_until
    session.flush()
    logger.info(f"Snoozed instance: id={instance_id}, until={snooze_until}")
    return instance


def expire_instance(
    session: Session,
    instance: ReminderInstance,
    now: datetime | None = None,
) -> None:
    """Mark an instance as expired (max sends reached).

    :param session: Database session.
    :param instance: The instance to expire.
    :param now: Current time (defaults to now).
    """
    if now is None:
        now = datetime.now(UTC)

    instance.status = ReminderStatus.EXPIRED.value
    instance.expired_at = now
    session.flush()
    logger.info(f"Expired instance: id={instance.id}, send_count={instance.send_count}")


def update_schedule_next_trigger(
    session: Session,
    schedule: ReminderSchedule,
    next_trigger: datetime,
) -> None:
    """Update the next trigger time for a recurring schedule.

    :param session: Database session.
    :param schedule: The schedule to update.
    :param next_trigger: The next trigger time.
    """
    schedule.next_trigger_at = next_trigger
    session.flush()
    logger.debug(f"Updated schedule next trigger: id={schedule.id}, next={next_trigger}")


def deactivate_schedule(
    session: Session,
    schedule_id: uuid_module.UUID,
) -> ReminderSchedule | None:
    """Deactivate (cancel) a reminder schedule.

    :param session: Database session.
    :param schedule_id: Schedule ID to deactivate.
    :returns: The deactivated schedule or None if not found.
    """
    schedule = get_schedule_by_id(session, schedule_id)
    if schedule is None:
        return None

    schedule.is_active = False
    session.flush()
    logger.info(f"Deactivated schedule: id={schedule_id}")
    return schedule


def list_schedules_for_chat(
    session: Session,
    chat_id: int,
    include_inactive: bool = False,
    limit: int = 50,
) -> list[ReminderSchedule]:
    """List reminder schedules for a chat.

    :param session: Database session.
    :param chat_id: Telegram chat ID.
    :param include_inactive: Whether to include deactivated schedules.
    :param limit: Maximum number of schedules to return.
    :returns: List of schedules.
    """
    query = session.query(ReminderSchedule).filter(ReminderSchedule.chat_id == chat_id)

    if not include_inactive:
        query = query.filter(ReminderSchedule.is_active.is_(True))

    return query.order_by(ReminderSchedule.next_trigger_at).limit(limit).all()


def get_active_instance_for_schedule(
    session: Session,
    schedule_id: uuid_module.UUID,
) -> ReminderInstance | None:
    """Get the active (unresolved) instance for a schedule.

    Returns the instance that is PENDING, ACTIVE, or SNOOZED.

    :param session: Database session.
    :param schedule_id: Schedule ID.
    :returns: The active instance or None.
    """
    return (
        session.query(ReminderInstance)
        .filter(
            ReminderInstance.schedule_id == schedule_id,
            ReminderInstance.status.in_(
                [
                    ReminderStatus.PENDING.value,
                    ReminderStatus.ACTIVE.value,
                    ReminderStatus.SNOOZED.value,
                ]
            ),
        )
        .first()
    )
