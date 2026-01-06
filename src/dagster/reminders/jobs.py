"""Dagster jobs for processing user reminders."""

from dagster import job
from src.dagster.reminders.ops import process_reminders_op


@job(
    name="process_reminders_job",
    description="Process and send due reminders (runs every 5 minutes).",
)
def process_reminders_job() -> None:
    """Process reminders job.

    Triggers due reminder schedules, creates instances, sends messages,
    and handles expiry for instances that have reached max attempts.
    """
    process_reminders_op()
