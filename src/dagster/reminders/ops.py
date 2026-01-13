"""Dagster ops for processing user reminders."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy.orm import Session

from dagster import Backoff, Jitter, OpExecutionContext, RetryPolicy, op
from src.database.connection import get_session
from src.database.reminders.models import ReminderInstance, ReminderSchedule
from src.database.reminders.operations import (
    create_reminder_instance,
    deactivate_schedule,
    expire_instance,
    get_active_instance_for_schedule,
    get_instances_to_send,
    get_schedules_to_trigger,
    mark_instance_sent,
    update_schedule_next_trigger,
)
from src.messaging.telegram import InlineKeyboardButton, InlineKeyboardMarkup, TelegramClient
from src.messaging.telegram.utils.config import get_telegram_settings
from src.messaging.telegram.utils.formatting import format_message

# Callback data prefix for reminder callbacks
REMINDER_CALLBACK_PREFIX = "remind:"

logger = logging.getLogger(__name__)

# Maximum number of error messages to include in notification
MAX_ERRORS_IN_NOTIFICATION = 5

# Retry policy for reminder ops
REMINDER_RETRY_POLICY = RetryPolicy(
    max_retries=1,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
    jitter=Jitter.FULL,
)


@dataclass
class ReminderStats:
    """Stats for reminder processing operations."""

    schedules_triggered: int = 0
    instances_created: int = 0
    reminders_sent: int = 0
    reminders_expired: int = 0
    errors: list[str] = field(default_factory=list)


def _notify_errors(context: OpExecutionContext, errors: list[str]) -> None:
    """Send error notification to the error bot if configured.

    :param context: Dagster execution context.
    :param errors: List of error messages.
    """
    if not errors:
        return

    settings = get_telegram_settings()
    if not settings.error_bot_token or not settings.error_chat_id:
        context.log.warning(
            "Error notification skipped: TELEGRAM_ERROR_BOT_TOKEN or "
            "TELEGRAM_ERROR_CHAT_ID not configured"
        )
        return

    client = TelegramClient(
        bot_token=settings.error_bot_token,
        chat_id=settings.error_chat_id,
    )

    error_summary = "\n".join(f"• {err}" for err in errors[:MAX_ERRORS_IN_NOTIFICATION])
    if len(errors) > MAX_ERRORS_IN_NOTIFICATION:
        extra = len(errors) - MAX_ERRORS_IN_NOTIFICATION
        error_summary += f"\n... and {extra} more"

    text = (
        f"**Reminder Processing Errors**\n\n"
        f"Job: `{context.job_name}`\n"
        f"Run ID: `{context.run_id}`\n"
        f"Errors: {len(errors)}\n\n"
        f"{error_summary}"
    )

    try:
        formatted_text, parse_mode = format_message(text)
        client.send_message_sync(formatted_text, parse_mode=parse_mode)
        context.log.info(f"Error notification sent: {len(errors)} errors")
    except Exception as e:
        context.log.error(f"Failed to send error notification: {e}")


def calculate_next_cron_trigger(cron_expression: str, after: datetime | None = None) -> datetime:
    """Calculate the next trigger time for a cron expression.

    :param cron_expression: Standard cron expression (5 fields).
    :param after: Calculate next trigger after this time. Defaults to now.
    :returns: Next trigger datetime in UTC.
    """
    if after is None:
        after = datetime.now(UTC)

    cron = croniter(cron_expression, after)
    next_time = cron.get_next(datetime)

    # Ensure timezone awareness
    if next_time.tzinfo is None:
        next_time = next_time.replace(tzinfo=UTC)

    return next_time


def _format_reminder_message(schedule: ReminderSchedule, instance: ReminderInstance) -> str:
    """Format a reminder message for sending via Telegram.

    :param schedule: The reminder schedule.
    :param instance: The reminder instance.
    :returns: Formatted Markdown message.
    """
    # send_count is incremented after sending, so add 1 for display
    send_number = instance.send_count + 1
    send_info = f"(Send {send_number}/{instance.max_sends})"

    return f"**Reminder** {send_info}\n\n{schedule.message}"


def _build_reminder_keyboard(instance_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard with acknowledge and snooze buttons.

    :param instance_id: The reminder instance ID.
    :returns: InlineKeyboardMarkup with action buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Done",
                    callback_data=f"{REMINDER_CALLBACK_PREFIX}ack:{instance_id}",
                ),
                InlineKeyboardButton(
                    text="Snooze 1h",
                    callback_data=f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:60",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Snooze 3h",
                    callback_data=f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:180",
                ),
                InlineKeyboardButton(
                    text="Tomorrow",
                    callback_data=f"{REMINDER_CALLBACK_PREFIX}snooze:{instance_id}:tomorrow",
                ),
            ],
        ]
    )


def _send_reminder(
    client: TelegramClient,
    schedule: ReminderSchedule,
    instance: ReminderInstance,
) -> None:
    """Send a reminder message via Telegram with inline keyboard.

    :param client: Telegram client.
    :param schedule: The reminder schedule.
    :param instance: The reminder instance being sent.
    """
    message = _format_reminder_message(schedule, instance)
    formatted_message, parse_mode = format_message(message)
    keyboard = _build_reminder_keyboard(str(instance.id))
    client.send_message_sync(
        formatted_message,
        chat_id=str(schedule.chat_id),
        parse_mode=parse_mode,
        reply_markup=keyboard,
    )


def _handle_instance_expiry(
    session: Session,
    instance: ReminderInstance,
    now: datetime,
    context: OpExecutionContext,
) -> None:
    """Handle expiry for an instance that has reached max sends.

    Expires the instance and deactivates one-time schedules to prevent
    new instances from being created.

    :param session: Database session.
    :param instance: The instance to expire.
    :param now: Current timestamp.
    :param context: Dagster execution context for logging.
    """
    expire_instance(session, instance, now)
    context.log.info(f"Expired instance {instance.id} after {instance.send_count} sends")

    # Deactivate one-time schedules after expiry to prevent new instances
    schedule = instance.schedule
    if not schedule.is_recurring:
        deactivate_schedule(session, schedule.id)
        context.log.info(f"Deactivated one-time schedule {schedule.id} after instance expiry")


@op(
    name="process_reminders",
    retry_policy=REMINDER_RETRY_POLICY,
    description="Process due reminders: trigger schedules, send messages, handle expiry.",
)
def process_reminders_op(context: OpExecutionContext) -> ReminderStats:
    """Process all due reminders.

    This op performs the following:
    1. Find schedules that are due to trigger and create instances
    2. Find instances that need to be sent (new, re-sends, un-snoozed)
    3. Send reminder messages via Telegram
    4. Handle expiry for instances that have reached max sends
    5. Update recurring schedule next trigger times

    :param context: Dagster execution context.
    :returns: Stats with counts of processed reminders.
    """
    context.log.info("Starting reminder processing")
    now = datetime.now(UTC)
    stats = ReminderStats()

    settings = get_telegram_settings()
    telegram_client = TelegramClient(
        bot_token=settings.bot_token,
        chat_id=settings.chat_id,
    )

    with get_session() as session:
        # Step 1: Process schedules that are due to trigger
        due_schedules = get_schedules_to_trigger(session, now)
        context.log.info(f"Found {len(due_schedules)} schedules due to trigger")
        stats.schedules_triggered = len(due_schedules)

        for schedule in due_schedules:
            try:
                # Check if there's already an active instance for this schedule
                existing_instance = get_active_instance_for_schedule(session, schedule.id)
                if existing_instance is not None:
                    context.log.debug(
                        f"Schedule {schedule.id} already has active instance {existing_instance.id}"
                    )
                    # Still need to update next trigger for recurring schedules
                    if schedule.is_recurring and schedule.cron_schedule:
                        next_trigger = calculate_next_cron_trigger(schedule.cron_schedule, now)
                        update_schedule_next_trigger(session, schedule, next_trigger)
                    continue

                # Create new instance
                instance = create_reminder_instance(session, schedule, now)
                stats.instances_created += 1
                context.log.info(f"Created instance {instance.id} for schedule {schedule.id}")

                # Update next trigger for recurring schedules
                if schedule.is_recurring and schedule.cron_schedule:
                    next_trigger = calculate_next_cron_trigger(schedule.cron_schedule, now)
                    update_schedule_next_trigger(session, schedule, next_trigger)
                    context.log.debug(
                        f"Updated recurring schedule {schedule.id} next trigger to {next_trigger}"
                    )

            except Exception as e:
                error_msg = f"Failed to process schedule {schedule.id}: {e}"
                context.log.error(error_msg)
                stats.errors.append(error_msg)

        # Step 2: Process instances that need to be sent
        instances_to_send = get_instances_to_send(session, now)
        context.log.info(f"Found {len(instances_to_send)} instances to send")

        for instance in instances_to_send:
            try:
                # Check if max sends reached - expire instead of sending
                if instance.send_count >= instance.max_sends:
                    _handle_instance_expiry(session, instance, now, context)
                    stats.reminders_expired += 1
                    continue

                # Send the reminder
                _send_reminder(telegram_client, instance.schedule, instance)
                mark_instance_sent(session, instance, now)
                stats.reminders_sent += 1
                context.log.info(
                    f"Sent reminder for instance {instance.id} "
                    f"(send {instance.send_count}/{instance.max_sends})"
                )

            except Exception as e:
                error_msg = f"Failed to send reminder for instance {instance.id}: {e}"
                context.log.error(error_msg)
                stats.errors.append(error_msg)

    context.log.info(
        f"Reminder processing complete: "
        f"triggered={stats.schedules_triggered}, "
        f"created={stats.instances_created}, "
        f"sent={stats.reminders_sent}, "
        f"expired={stats.reminders_expired}, "
        f"errors={len(stats.errors)}"
    )

    _notify_errors(context, stats.errors)

    return stats
