"""Dagster jobs for sending alerts."""

from dagster import job
from src.dagster.alerts.ops import (
    send_daily_task_alerts_op,
    send_monthly_goal_alerts_op,
    send_weekly_reading_alerts_op,
)


@job(
    name="daily_task_alerts_job",
    description="Send daily task reminder alerts via Telegram.",
)
def daily_task_alerts_job() -> None:
    """Job for sending daily task reminders.

    Sends a summary of overdue tasks, tasks due today, and high
    priority tasks due this week.
    """
    send_daily_task_alerts_op()


@job(
    name="monthly_goal_alerts_job",
    description="Send monthly goal review alerts via Telegram.",
)
def monthly_goal_alerts_job() -> None:
    """Job for sending monthly goal reviews.

    Sends a summary of all active goals with their progress.
    """
    send_monthly_goal_alerts_op()


@job(
    name="weekly_reading_alerts_job",
    description="Send weekly reading list reminder alerts via Telegram.",
)
def weekly_reading_alerts_job() -> None:
    """Job for sending weekly reading list reminders.

    Sends a summary of high priority and stale reading items.
    """
    send_weekly_reading_alerts_op()
