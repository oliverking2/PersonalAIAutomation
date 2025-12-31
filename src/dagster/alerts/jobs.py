"""Dagster jobs for sending alerts."""

from dagster import job
from src.dagster.alerts.ops import (
    send_overdue_task_alerts_op,
    send_personal_task_alerts_op,
    send_weekly_goal_alerts_op,
    send_weekly_reading_alerts_op,
    send_work_task_alerts_op,
)


@job(
    name="work_task_alerts_job",
    description="Send daily work task reminder alerts via Telegram (9am).",
)
def work_task_alerts_job() -> None:
    """Job for sending work task reminders.

    Sends a summary of work tasks due today. On Mondays, also includes
    high and medium priority work tasks for the week.
    """
    send_work_task_alerts_op()


@job(
    name="personal_task_alerts_job",
    description="Send daily personal task reminder alerts via Telegram (6pm).",
)
def personal_task_alerts_job() -> None:
    """Job for sending personal task reminders.

    Sends a summary of personal/photography tasks due today. On Saturdays,
    also includes high and medium priority personal tasks for the weekend.
    """
    send_personal_task_alerts_op()


@job(
    name="overdue_task_alerts_job",
    description="Send daily overdue/incomplete task reminder alerts via Telegram (9pm).",
)
def overdue_task_alerts_job() -> None:
    """Job for sending overdue task reminders.

    Sends a summary of all tasks due today that are incomplete,
    plus all overdue tasks.
    """
    send_overdue_task_alerts_op()


@job(
    name="weekly_goal_alerts_job",
    description="Send weekly goal review alerts via Telegram (Monday 7am).",
)
def weekly_goal_alerts_job() -> None:
    """Job for sending weekly goal reviews.

    Sends a summary of goals that are in progress or have a due date
    within the next 3 months.
    """
    send_weekly_goal_alerts_op()


@job(
    name="weekly_reading_alerts_job",
    description="Send weekly reading list reminder alerts via Telegram.",
)
def weekly_reading_alerts_job() -> None:
    """Job for sending weekly reading list reminders.

    Sends a summary of high priority and stale reading items.
    """
    send_weekly_reading_alerts_op()
