"""Dagster definitions for reminder jobs and schedules."""

from dagster import Definitions
from src.dagster.reminders.jobs import process_reminders_job
from src.dagster.reminders.schedules import process_reminders_schedule

defs = Definitions(
    jobs=[process_reminders_job],
    schedules=[process_reminders_schedule],
)
