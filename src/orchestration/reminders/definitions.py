"""Dagster definitions for reminder jobs and schedules."""

from dagster import Definitions

from src.orchestration.reminders.jobs import process_reminders_job
from src.orchestration.reminders.schedules import process_reminders_schedule

defs = Definitions(
    jobs=[process_reminders_job],
    schedules=[process_reminders_schedule],
)
