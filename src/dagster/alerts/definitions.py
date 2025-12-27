"""Dagster definitions for alert jobs and schedules."""

from dagster import Definitions
from src.dagster.alerts.jobs import (
    daily_task_alerts_job,
    monthly_goal_alerts_job,
    weekly_reading_alerts_job,
)
from src.dagster.alerts.schedules import (
    daily_task_alert_schedule,
    monthly_goal_alert_schedule,
    weekly_reading_alert_schedule,
)

defs = Definitions(
    jobs=[
        daily_task_alerts_job,
        monthly_goal_alerts_job,
        weekly_reading_alerts_job,
    ],
    schedules=[
        daily_task_alert_schedule,
        monthly_goal_alert_schedule,
        weekly_reading_alert_schedule,
    ],
)
