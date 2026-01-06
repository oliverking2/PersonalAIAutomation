"""Dagster schedules for processing user reminders."""

from dagster import ScheduleDefinition
from src.dagster.reminders.jobs import process_reminders_job

# Process reminders every 5 minutes
process_reminders_schedule = ScheduleDefinition(
    job=process_reminders_job,
    cron_schedule="*/5 * * * *",
    execution_timezone="UTC",
)
