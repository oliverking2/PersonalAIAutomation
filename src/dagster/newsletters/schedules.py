"""Dagster schedules for newsletter automation."""

from dagster import ScheduleDefinition
from src.dagster.newsletters.jobs import (
    medium_pipeline_job,
    newsletter_pipeline_job,
    substack_pipeline_job,
)

# Run newsletter pipeline every hour at :00 during daytime
hourly_newsletter_schedule = ScheduleDefinition(
    job=newsletter_pipeline_job,
    cron_schedule="0 8-21 * * *",
    execution_timezone="UTC",
)

# Run Substack pipeline every hour at :30 during daytime
hourly_substack_schedule = ScheduleDefinition(
    job=substack_pipeline_job,
    cron_schedule="30 8-21 * * *",
    execution_timezone="UTC",
)

# Run Medium pipeline once daily at 8:15am UTC
daily_medium_schedule = ScheduleDefinition(
    job=medium_pipeline_job,
    cron_schedule="15 8 * * *",
    execution_timezone="UTC",
)
