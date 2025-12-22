"""Dagster schedules for newsletter automation."""

from dagster import ScheduleDefinition
from src.dagster.newsletters.jobs import newsletter_pipeline_job

# Run newsletter pipeline every hour at :00
hourly_newsletter_schedule = ScheduleDefinition(
    job=newsletter_pipeline_job,
    cron_schedule="0 * * * *",
    execution_timezone="UTC",
)
