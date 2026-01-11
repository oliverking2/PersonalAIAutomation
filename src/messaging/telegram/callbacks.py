"""Callback handlers for Telegram inline keyboard buttons."""

import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from src.database.connection import get_session
from src.database.reminders import (
    ReminderStatus,
    acknowledge_instance,
    deactivate_schedule,
    get_instance_by_id,
    snooze_instance,
)
from src.messaging.telegram.client import TelegramClient
from src.messaging.telegram.models import CallbackQuery

logger = logging.getLogger(__name__)

# Callback data prefix for reminder callbacks
REMINDER_CALLBACK_PREFIX = "remind:"

# Minimum number of parts in callback data (prefix:action:instance_id)
MIN_CALLBACK_PARTS = 3

# Index for optional parameter in callback data
PARAM_INDEX = 3


class ReminderAction(StrEnum):
    """Actions for reminder callbacks."""

    ACKNOWLEDGE = "ack"
    SNOOZE = "snooze"


class CallbackResult:
    """Result of handling a callback query."""

    def __init__(
        self,
        answer_text: str,
        show_alert: bool = False,
        edit_text: str | None = None,
    ) -> None:
        """Initialise callback result.

        :param answer_text: Text to show in toast/alert.
        :param show_alert: Whether to show as alert instead of toast.
        :param edit_text: Optional new text for the message.
        """
        self.answer_text = answer_text
        self.show_alert = show_alert
        self.edit_text = edit_text


def parse_reminder_callback(data: str) -> tuple[ReminderAction, UUID, str | None] | None:
    """Parse reminder callback data.

    Format: ``remind:action:instance_id[:param]``

    :param data: Callback data string.
    :returns: Tuple of (action, instance_id, param) or None if invalid.
    """
    if not data.startswith(REMINDER_CALLBACK_PREFIX):
        return None

    parts = data.split(":")
    if len(parts) < MIN_CALLBACK_PARTS:
        logger.warning(f"Invalid reminder callback data: {data}")
        return None

    try:
        action = ReminderAction(parts[1])
        instance_id = UUID(parts[2])
        param = parts[PARAM_INDEX] if len(parts) > PARAM_INDEX else None
        return action, instance_id, param
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse reminder callback: {data}, error={e}")
        return None


def _get_tomorrow_morning() -> datetime:
    """Get tomorrow at 8am in UTC.

    :returns: Datetime for tomorrow 8am UTC.
    """
    now = datetime.now(UTC)
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)


def _calculate_snooze_time(param: str | None) -> tuple[datetime, str]:
    """Calculate snooze until time and description.

    :param param: Snooze parameter (minutes or 'tomorrow').
    :returns: Tuple of (snooze_until datetime, description string).
    """
    now = datetime.now(UTC)
    default_minutes = 60

    if param == "tomorrow":
        return _get_tomorrow_morning(), "tomorrow morning"

    try:
        minutes = int(param) if param else default_minutes
    except ValueError:
        minutes = default_minutes

    snooze_until = now + timedelta(minutes=minutes)
    snooze_desc = f"{minutes // 60}h" if minutes >= 60 else f"{minutes}m"  # noqa: PLR2004
    return snooze_until, snooze_desc


def handle_reminder_callback(
    data: str,
    original_text: str | None = None,
) -> CallbackResult:
    """Handle a reminder callback from an inline keyboard button.

    :param data: Callback data string from the button.
    :param original_text: Original message text (for editing).
    :returns: CallbackResult with response information.
    """
    parsed = parse_reminder_callback(data)
    if parsed is None:
        return CallbackResult(answer_text="Invalid callback data", show_alert=True)

    action, instance_id, param = parsed
    logger.info(
        f"Handling reminder callback: action={action}, instance_id={instance_id}, param={param}"
    )

    with get_session() as session:
        instance = get_instance_by_id(session, instance_id)
        if instance is None:
            return CallbackResult(answer_text="Reminder not found", show_alert=True)

        # Check if already resolved
        resolved_statuses = [ReminderStatus.ACKNOWLEDGED.value, ReminderStatus.EXPIRED.value]
        if instance.status in resolved_statuses:
            return CallbackResult(
                answer_text=f"Reminder already {instance.status}", show_alert=True
            )

        schedule = instance.schedule
        now = datetime.now(UTC)

        if action == ReminderAction.ACKNOWLEDGE:
            acknowledge_instance(session, instance_id, now)
            if not schedule.is_recurring:
                deactivate_schedule(session, schedule.id)

            logger.info(f"Acknowledged reminder: instance_id={instance_id}")
            edit_text = f"{original_text}\n\n<i>Acknowledged</i>" if original_text else None
            return CallbackResult(answer_text="Reminder acknowledged!", edit_text=edit_text)

        if action == ReminderAction.SNOOZE:
            snooze_until, snooze_desc = _calculate_snooze_time(param)
            snooze_instance(session, instance_id, snooze_until)
            logger.info(f"Snoozed reminder: instance_id={instance_id}, until={snooze_until}")

            edit_text = None
            if original_text:
                snooze_time = snooze_until.strftime("%H:%M")
                edit_text = f"{original_text}\n\n<i>Snoozed until {snooze_time}</i>"
            return CallbackResult(answer_text=f"Snoozed for {snooze_desc}", edit_text=edit_text)

    return CallbackResult(answer_text="Unknown action", show_alert=True)


async def process_callback_query(
    client: TelegramClient,
    callback_query: CallbackQuery,
) -> None:
    """Process a callback query from Telegram.

    :param client: Telegram client for sending responses.
    :param callback_query: The callback query to process.
    """
    if not callback_query.data:
        logger.warning(f"Callback query without data: id={callback_query.id}")
        await client.answer_callback_query(callback_query.id, "Invalid callback")
        return

    # Check if this is a reminder callback
    if not callback_query.data.startswith(REMINDER_CALLBACK_PREFIX):
        logger.debug(f"Non-reminder callback: {callback_query.data}")
        await client.answer_callback_query(callback_query.id, "Unknown callback")
        return

    # Get original message text for editing
    original_text = callback_query.message.text if callback_query.message else None

    # Handle the callback
    result = handle_reminder_callback(callback_query.data, original_text)

    # Answer the callback query
    await client.answer_callback_query(
        callback_query.id,
        text=result.answer_text,
        show_alert=result.show_alert,
    )

    # Edit the message if needed
    if result.edit_text and callback_query.message:
        chat_id = str(callback_query.message.chat.id)
        message_id = callback_query.message.message_id
        await client.edit_message_text(
            text=result.edit_text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,  # Remove the keyboard
        )


def process_callback_query_sync(
    client: TelegramClient,
    callback_query: CallbackQuery,
) -> None:
    """Process a callback query from Telegram (synchronous version).

    :param client: Telegram client for sending responses.
    :param callback_query: The callback query to process.
    """
    if not callback_query.data:
        logger.warning(f"Callback query without data: id={callback_query.id}")
        client.answer_callback_query_sync(callback_query.id, "Invalid callback")
        return

    # Check if this is a reminder callback
    if not callback_query.data.startswith(REMINDER_CALLBACK_PREFIX):
        logger.debug(f"Non-reminder callback: {callback_query.data}")
        client.answer_callback_query_sync(callback_query.id, "Unknown callback")
        return

    # Get original message text for editing
    original_text = callback_query.message.text if callback_query.message else None

    # Handle the callback
    result = handle_reminder_callback(callback_query.data, original_text)

    # Answer the callback query
    client.answer_callback_query_sync(
        callback_query.id,
        text=result.answer_text,
        show_alert=result.show_alert,
    )

    # Edit the message if needed
    if result.edit_text and callback_query.message:
        chat_id = str(callback_query.message.chat.id)
        message_id = callback_query.message.message_id
        client.edit_message_text_sync(
            text=result.edit_text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,  # Remove the keyboard
        )
