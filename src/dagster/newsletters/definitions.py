"""Dagster definitions for newsletter automation."""

from dagster import Definitions
from src.dagster.newsletters.jobs import (
    medium_pipeline_job,
    newsletter_pipeline_job,
    substack_pipeline_job,
)
from src.dagster.newsletters.schedules import (
    daily_medium_schedule,
    hourly_newsletter_schedule,
    hourly_substack_schedule,
)

defs = Definitions(
    jobs=[newsletter_pipeline_job, substack_pipeline_job, medium_pipeline_job],
    schedules=[hourly_newsletter_schedule, hourly_substack_schedule, daily_medium_schedule],
)
