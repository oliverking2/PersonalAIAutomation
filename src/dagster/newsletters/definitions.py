"""Dagster definitions for newsletter automation."""

from dagster import Definitions
from src.dagster.newsletters.jobs import newsletter_pipeline_job
from src.dagster.newsletters.schedules import hourly_newsletter_schedule

defs = Definitions(
    jobs=[newsletter_pipeline_job],
    schedules=[hourly_newsletter_schedule],
)
