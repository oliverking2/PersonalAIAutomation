"""Dagster ops for sending alerts."""

from dataclasses import dataclass

from dagster import Backoff, Jitter, OpExecutionContext, RetryPolicy, op
from src.alerts import (
    AlertService,
    AlertType,
    GoalAlertProvider,
    ReadingAlertProvider,
    TaskAlertProvider,
)
from src.api.client import InternalAPIClient
from src.database.connection import get_session
from src.telegram import TelegramClient
from src.telegram.utils.config import get_telegram_settings

# Retry policy for alert ops
ALERT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    delay=60,
    backoff=Backoff.EXPONENTIAL,
    jitter=Jitter.FULL,
)


@dataclass
class AlertStats:
    """Stats for alert operations."""

    alerts_sent: int
    alerts_skipped: int
    errors: list[str]


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
    name="send_daily_task_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send daily task reminder alerts.",
)
def send_daily_task_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send daily task reminder alerts.

    Sends a summary of overdue tasks, tasks due today, and high priority
    tasks due this week.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting daily task alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = TaskAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.DAILY_TASK])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Daily task alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )
    return stats


@op(
    name="send_monthly_goal_alerts",
    retry_policy=ALERT_RETRY_POLICY,
    description="Send monthly goal review alerts.",
)
def send_monthly_goal_alerts_op(context: OpExecutionContext) -> AlertStats:
    """Send monthly goal review alerts.

    Sends a summary of all active goals with their progress.

    :param context: Dagster execution context.
    :returns: Stats with counts of sent/skipped alerts.
    """
    context.log.info("Starting monthly goal alerts")

    telegram_client = _get_telegram_client()

    with InternalAPIClient() as api_client:
        provider = GoalAlertProvider(api_client)

        with get_session() as session:
            service = AlertService(
                session=session,
                telegram_client=telegram_client,
                providers=[provider],
            )
            result = service.send_alerts(alert_types=[AlertType.MONTHLY_GOAL])

    stats = AlertStats(
        alerts_sent=result.alerts_sent,
        alerts_skipped=result.alerts_skipped,
        errors=result.errors,
    )

    context.log.info(
        f"Monthly goal alerts complete: {stats.alerts_sent} sent, "
        f"{stats.alerts_skipped} skipped, {len(stats.errors)} errors"
    )
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
    return stats
