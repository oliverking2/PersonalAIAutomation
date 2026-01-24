"""Dagster ops for sending alerts."""

import logging
from dataclasses import dataclass

from dagster import Backoff, Jitter, OpExecutionContext, RetryPolicy, op

from src.alerts import (
    AlertService,
    AlertType,
    BinScheduleAlertProvider,
    GoalAlertProvider,
    OverdueTaskAlertProvider,
    PersonalTaskAlertProvider,
    ReadingAlertProvider,
    WorkTaskAlertProvider,
)
from src.api.client import InternalAPIClient
from src.database.connection import get_session
from src.messaging.telegram import TelegramClient
from src.messaging.telegram.utils.config import get_telegram_settings
from src.messaging.telegram.utils.formatting import format_message

logger = logging.getLogger(__name__)

# Maximum number of error messages to include in notification
MAX_ERRORS_IN_NOTIFICATION = 5

# Retry policy for alert ops
ALERT_RETRY_POLICY = RetryPolicy(
    max_retries=1,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
    jitter=Jitter.FULL,
)


@dataclass
class AlertStats:
    """Stats for alert operations."""

    alerts_sent: int
    alerts_skipped: int
    errors: list[str]


def _notify_errors(context: OpExecutionContext, alert_type: str, errors: list[str]) -> None:
    """Send error notification to the error bot if configured.

    :param context: Dagster execution context.
    :param alert_type: Type of alert that had errors.
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
        f"**Alert Op Errors: {alert_type}**\n\n"
        f"Job: `{context.job_name}`\n"
        f"Run ID: `{context.run_id}`\n"
        f"Errors: {len(errors)}\n\n"
        f"{error_summary}"
    )

    try:
        formatted_text, parse_mode = format_message(text)
        client.send_message_sync(formatted_text, parse_mode=parse_mode)
        context.log.info(f"Error notification sent for {alert_type}: {len(errors)} errors")
    except Exception as e:
        context.log.error(f"Failed to send error notification: {e}")


def _get_telegram_client() -> TelegramClient:
    """Create a Telegram client from settings.

    :returns: Configured TelegramClient.
    """
    settings = get_telegram_settings()
    return TelegramClient(
        bot_token=settings.bot_token,
        chat_id=settings.chat_id,
    )


@op(
    name="send_work_task_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send daily work task reminder alerts (9am).",
)
def send_work_task_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send work task reminder alerts.

    Sends a summary of work tasks due today. On Mondays, also includes
    high and medium priority work tasks for the week.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting work task alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = WorkTaskAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.DAILY_TASK_WORK])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Work task alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )

    _notify_errors(context, "Work Task Alerts", stats.errors)

    return stats


@op(
    name="send_personal_task_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send daily personal task reminder alerts (6pm).",
)
def send_personal_task_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send personal task reminder alerts.

    Sends a summary of personal/photography tasks due today. On Saturdays,
    also includes high and medium priority personal tasks for the weekend.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting personal task alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = PersonalTaskAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.DAILY_TASK_PERSONAL])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Personal task alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )

    _notify_errors(context, "Personal Task Alerts", stats.errors)

    return stats


@op(
    name="send_overdue_task_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send daily overdue/incomplete task reminder alerts (9pm).",
)
def send_overdue_task_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send overdue task reminder alerts.

    Sends a summary of all tasks due today that are incomplete,
    plus all overdue tasks.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting overdue task alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = OverdueTaskAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.DAILY_TASK_OVERDUE])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Overdue task alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )

    _notify_errors(context, "Overdue Task Alerts", stats.errors)

    return stats


@op(
    name="send_weekly_goal_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send weekly goal review alerts (Monday 7am).",
)
def send_weekly_goal_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send weekly goal review alerts.

    Sends a summary of goals that are in progress or have a due date
    within the next 3 months.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting weekly goal alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = GoalAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.WEEKLY_GOAL])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Weekly goal alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )

    _notify_errors(context, "Weekly Goal Alerts", stats.errors)

    return stats


@op(
    name="send_weekly_reading_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send weekly reading list reminder alerts.",
)
def send_weekly_reading_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send weekly reading list reminder alerts.

    Sends a summary of high priority and stale reading items.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting weekly reading alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = ReadingAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.WEEKLY_READING])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Weekly reading alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )

    _notify_errors(context, "Weekly Reading Alerts", stats.errors)

    return stats


@op(
    name="send_bin_schedule_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send weekly bin collection reminder alerts (Sunday 8pm).",
)
def send_bin_schedule_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send bin collection reminder alerts.

    Sends a reminder indicating which bin (General Waste or Recycling)
    to put out for collection the next day.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting bin schedule alerts")

    telegram_client = _get_telegram_client()
    provider = BinScheduleAlertProvider()

    with get_session() as session:
        service = AlertService(
            session=session,
            telegram_client=telegram_client,
            providers=[provider],
        )
        result = service.send_alerts(alert_types=[AlertType.BIN_SCHEDULE])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Bin schedule alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )

    _notify_errors(context, "Bin Schedule Alerts", stats.errors)

    return stats
